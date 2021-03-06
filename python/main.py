import sys, os.path, cv2, math, colorsys, signal, threading, multiprocessing
import numpy as np
from PIL import Image, ImageDraw
from multiprocessing import Process, Queue, JoinableQueue

IMAGE_BACKGROUND = (0,0,0)
VARIANCE_THRESHOLD = 100
MIN_PIECE_SIZE = 2
OUTPUT_SCALE = 4
BLOCK_HEIGHT_FACTOR = 1000
MAX_HEIGHT = 15
VIEW_DISTANCE = 1000
TILT =  math.pi / 2
BORDER_SIZE=100
WORKER_COUNT = max(1, multiprocessing.cpu_count() - 1)
print('worker count=' + str(WORKER_COUNT))


class ImagePiece:
    def __init__(self, image, x1, y1, x2, y2):
        self.image = image
        self.image_data = image.load()
        self.x1 = x1
        self.y1 = y1
        self.x2 = x2
        self.y2 = y2
        self.width = x2 - x1
        self.height = y2 - y1
        self.variance = None
        self.rgb_colour = None

        full_image_width, full_image_height = image.size
        self.area_fraction = (self.width * self.height) / (full_image_width * full_image_height)

    def split(self):
        if (self.width < self.height):
            y_split = int(round((self.y1 + self.y2) / 2))
            top_piece = ImagePiece(self.image, self.x1, self.y1, self.x2, y_split)
            bottom_piece = ImagePiece(self.image, self.x1, y_split+1, self.x2, self.y2)
            return top_piece, bottom_piece
        else:
            x_split = int(round((self.x1 + self.x2) / 2))
            left_piece = ImagePiece(self.image, self.x1, self.y1, x_split, self.y2)
            right_piece = ImagePiece(self.image, x_split+1, self.y1, self.x2, self.y2)
            return left_piece, right_piece

    def get_variance(self):
        if self.variance is None:
            if self.width <= MIN_PIECE_SIZE and self.height <= MIN_PIECE_SIZE:
                self.variance = 0

            else:
                min_v = 1000
                max_v = 0
                for x in range(self.x1, self.x2+1):
                    for y in range(self.y1, self.y2+1):
                        r,g,b = self.image_data[x,y]
                        v = r + g + b
                        min_v = min(min_v, v)
                        max_v = max(max_v, v)

                self.variance = max_v - min_v

        return self.variance

    def get_rgb_colour(self):
        if self.rgb_colour is None:
            r_total = g_total = b_total = count = 0

            for x in range(self.x1, self.x2+1):
                for y in range(self.y1, self.y2+1):
                    r,g,b = self.image_data[x,y]
                    r_total += r
                    g_total += g
                    b_total += b
                    count += 1

            self.rgb_colour = (int(r_total/count), int(g_total/count), int(b_total/count))

        return self.rgb_colour

class ImagePieceBuilder:
    def __init__(self, image):
        self.image = image

    def build_piece(self, x1, y1, x2, y2):
        return ImagePiece(self.image, x1, y1, x2, y2)

class CoordTransformer:
    def __init__(self, view_width, view_height, view_distance):
        self.view_width = view_width
        self.view_height = view_height
        self.view_distance = view_distance

    def __tilt(self, x, y, z):
        return {
            'x': x,
            'y': (z-VIEW_DISTANCE) * math.sin(TILT) + (y + self.view_height/2) * math.cos(TILT) - self.view_height/2 ,
            'z': (z-VIEW_DISTANCE) * math.cos(TILT) - (y + self.view_height/2) * math.sin(TILT) + VIEW_DISTANCE
        }

    def transform(self, x, y, height):
        x3d_flat = x - self.view_width/2
        y3d_flat = height - self.view_height/2
        z3d_flat = VIEW_DISTANCE + self.view_height - y

        tilted_coords = self.__tilt(x3d_flat, y3d_flat, z3d_flat)

        transformed_x = tilted_coords['x'] * VIEW_DISTANCE / tilted_coords['z']
        transformed_y = tilted_coords['y'] * VIEW_DISTANCE / tilted_coords['z']

        return {
            'x': transformed_x + self.view_width / 2,
            'y': -transformed_y + self.view_height / 2,
            'distance': tilted_coords['x'] * tilted_coords['x'] + tilted_coords['y'] * tilted_coords['y'] + tilted_coords['z'] * tilted_coords['z'] }


class PieceRenderer:
    def __init__(self, image):
        self.image = image

        image_width, image_height = image.size
        self.transformer = CoordTransformer(image_width, image_height, VIEW_DISTANCE)
        self.image_width = image_width

    def __point(self, p):
        return p['x'] + BORDER_SIZE, p['y'] + BORDER_SIZE

    def __to_hsl(self, rgb_colour, lightness_change):
        h, l, s = colorsys.rgb_to_hls(rgb_colour[0]/255, rgb_colour[1]/255, rgb_colour[2]/255)
        return 'hsl({},{}%,{}%)'.format(int(h * 360), int(s * 100), min(int(l * lightness_change * 100), 100))

    def __colour_top_face(self, top_colour):
        return self.__to_hsl(top_colour, 1)

    def __colour_front_face(self, top_colour):
        return self.__to_hsl(top_colour, 0.8)

    def __colour_back_face(self, top_colour):
        return self.__to_hsl(top_colour, 1.2)

    def __colour_left_face(self, top_colour):
        return self.__to_hsl(top_colour, 1.4)

    def __colour_right_face(self, top_colour):
        return self.__to_hsl(top_colour, 0.6)

    def __find_closest_distance(self, points):
        return min(p['distance'] for p in points)

    def get_polygons(self, image_piece):
        x1 = image_piece.x1 * OUTPUT_SCALE
        y1 = image_piece.y1 * OUTPUT_SCALE
        x2 = (image_piece.x2 + 1) * OUTPUT_SCALE - 1
        y2 = (image_piece.y2 + 1) * OUTPUT_SCALE - 1
        h1 = min(image_piece.area_fraction * BLOCK_HEIGHT_FACTOR, MAX_HEIGHT) * OUTPUT_SCALE
        h2 = 0

        tbl = self.transformer.transform(x1, y1, h1)
        tbr = self.transformer.transform(x2, y1, h1)
        tfl = self.transformer.transform(x1, y2, h1)
        tfr = self.transformer.transform(x2, y2, h1)

        bbl = self.transformer.transform(x1, y1, h2)
        bbr = self.transformer.transform(x2, y1, h2)
        bfl = self.transformer.transform(x1, y2, h2)
        bfr = self.transformer.transform(x2, y2, h2)

        rgb_colour = image_piece.get_rgb_colour()

        return [
            # Top face
            (self.__point(tbl), self.__point(tbr), self.__point(tfr), self.__point(tfl), self.__colour_top_face(rgb_colour), self.__find_closest_distance((tbl, tbr, tfr, tfl))),
            # Front face
            (self.__point(tfl), self.__point(tfr), self.__point(bfr), self.__point(bfl), self.__colour_front_face(rgb_colour), self.__find_closest_distance((tfl, tfr, bfr, bfl))),
            # Back face
            (self.__point(tbl), self.__point(tbr), self.__point(bbr), self.__point(bbl), self.__colour_back_face(rgb_colour), self.__find_closest_distance((tbl, tbr, bbr, bbl))),
            # Right face
            (self.__point(tbr), self.__point(bbr), self.__point(bfr), self.__point(tfr), self.__colour_right_face(rgb_colour), self.__find_closest_distance((tbr, bbr, bfr, tfr))),
            # Left face
            (self.__point(tbl), self.__point(bbl), self.__point(bfl), self.__point(tfl), self.__colour_left_face(rgb_colour), self.__find_closest_distance((tbl, bbl, bfl, tfl)))
        ]

def transform_frame(frame_in, width_in, height_in):
    img_in = Image.fromarray(frame_in)
    img_out = Image.new('RGB', (width_in * OUTPUT_SCALE + 2 * BORDER_SIZE, height_in * OUTPUT_SCALE + 2 * BORDER_SIZE), IMAGE_BACKGROUND)

    work_queue = [ImagePiece(img_in, 0, 0, width_in-1, height_in-1)]
    finished_queue = []

    def allocate_to_queue(image_piece):
        if image_piece.get_variance() < VARIANCE_THRESHOLD:
            finished_queue.append(image_piece)
        else:
            work_queue.append(image_piece)

    while work_queue:
        next_piece = work_queue.pop()
        half_piece_1, half_piece_2 = next_piece.split()
        allocate_to_queue(half_piece_1)
        allocate_to_queue(half_piece_2)

    renderer = PieceRenderer(img_out)
    polygons = [polygon for piece in finished_queue for polygon in renderer.get_polygons(piece)]

    def get_polygon_distance(p):
        return p[5]

    polygons.sort(key=get_polygon_distance, reverse=True)

    image_draw = ImageDraw.Draw(img_out)
    [image_draw.polygon([p[0], p[1], p[2], p[3]], fill=p[4]) for p in polygons]

    frame_out = np.asarray(img_out)

    return frame_out

STOP_WORKING = None
work_queue = JoinableQueue()
finished_queue = Queue()

class Workers:
    def __init__(self, work_queue, work_function):
        self.threads = []
        self.work_queue = work_queue
        for i in range(WORKER_COUNT):
            self.threads.append(Process(target=work_function))

    def start(self):
        [thread.start() for thread in self.threads]

    def stop(self):
        for _ in self.threads:
            self.work_queue.put(STOP_WORKING)

def work():
    while True:
        work_item = work_queue.get()
        if work_item == STOP_WORKING:
            work_queue.task_done()
            break
        frame_id, next_frame, width_in, height_in = work_item
        if not user_stop:
            print('Processing frame ' + str(frame_id))
            finished_queue.put((frame_id, transform_frame(next_frame, width_in, height_in)))
        work_queue.task_done()

user_stop = False

def process(in_file, out_file):
    video_in = cv2.VideoCapture(in_file)
    fps = video_in.get(cv2.CAP_PROP_FPS)
    width_in = int(video_in.get(cv2.CAP_PROP_FRAME_WIDTH))
    height_in = int(video_in.get(cv2.CAP_PROP_FRAME_HEIGHT))

    video_out = cv2.VideoWriter(out_file, cv2.VideoWriter_fourcc(*'MP4V'), fps, (width_in * OUTPUT_SCALE + 2 * BORDER_SIZE, height_in * OUTPUT_SCALE + 2 * BORDER_SIZE))

    def on_user_stop(_1, _2):
        global user_stop
        user_stop = True

    signal.signal(signal.SIGINT, on_user_stop)

    workers = Workers(work_queue, work)

    frame_count = 0
    workers.start()
    while video_in.isOpened() and not user_stop:
        frame_count += 1
        found_frame, frame_in = video_in.read()
        if found_frame:
            work_queue.put((frame_count, frame_in, width_in, height_in))

        else:
            break

    workers.stop()
    work_queue.join()

    finished_list = []
    while not finished_queue.empty():
        finished_list.append(finished_queue.get())
    finished_list.sort(key=lambda t: t[0])
    print('Writing video...')
    [video_out.write(frame_details[1]) for frame_details in finished_list]
    video_out.release()

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print('Usage: python {} <input file>'.format(sys.argv[0]), file=sys.stderr)
    else:
        input_file = sys.argv[1]
        if not os.path.isfile(input_file):
            print('Cannot find file {}'.format(input_file), file=sys.stderr)
        else:
            out_file = 'out.mp4'
            if os.path.isfile(out_file):
                os.remove(out_file)
            process(input_file, out_file)