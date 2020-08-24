import sys, os.path, cv2
import numpy as np
from PIL import Image, ImageDraw

IMAGE_BACKGROUND = (255, 255, 255)
VARIANCE_THRESHOLD = 200
MIN_PIECE_SIZE = 5
OUTPUT_SCALE = 2
BLOCK_HEIGHT_FACTOR = 1000
MAX_HEIGHT = 50
VIEW_DISTANCE = 1000

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
        self.colour = None

        full_image_width, full_image_height = image.size
        self.area_fraction = (self.width * self.height) / (full_image_width * full_image_height)

    def split(self):
        if (self.width < self.height):
            y_split = int((self.y1 + self.y2) / 2)
            top_piece = ImagePiece(self.image, self.x1, self.y1, self.x2, y_split)
            bottom_piece = ImagePiece(self.image, self.x1, y_split+1, self.x2, self.y2)
            return top_piece, bottom_piece
        else:
            x_split = int((self.x1 + self.x2) / 2)
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

    def get_colour(self):
        if self.colour is None:
            r_total = g_total = b_total = count = 0

            for x in range(self.x1, self.x2+1):
                for y in range(self.y1, self.y2+1):
                    r,g,b = self.image_data[x,y]
                    r_total += r
                    g_total += g
                    b_total += b
                    count += 1

            self.colour = (int(r_total/count), int(g_total/count), int(b_total/count))

        return self.colour

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

    def transform(self, x, y, height):
        x3d_flat = x - self.view_width/2
        y3d_flat = height - self.view_height/2
        z3d_flat = VIEW_DISTANCE + self.view_height - y

        transformed_x = x3d_flat * VIEW_DISTANCE / z3d_flat
        transformed_y  = y3d_flat * VIEW_DISTANCE / z3d_flat

        return {'x': transformed_x + self.view_width / 2, 'y': -transformed_y + self.view_height / 2}


class PieceRenderer:
    def __init__(self, image):
        self.image = image
        self.image_draw = ImageDraw.Draw(image)

        image_width, image_height = image.size
        self.transformer = CoordTransformer(image_width, image_height, VIEW_DISTANCE)
        self.image_width = image_width

    def __point(self, p):
        return p['x'], p['y']

    def draw(self, image_piece):
        x1 = image_piece.x1 * OUTPUT_SCALE
        y1 = image_piece.y1 * OUTPUT_SCALE
        x2 = image_piece.x2 * OUTPUT_SCALE
        y2 = image_piece.y2 * OUTPUT_SCALE
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

        # Top face
        self.image_draw.polygon([
            self.__point(tbl),
            self.__point(tbr),
            self.__point(tfr),
            self.__point(tfl)
        ],fill=image_piece.get_colour())

        # Front face
        self.image_draw.polygon([
            self.__point(tfl),
            self.__point(tfr),
            self.__point(bfr),
            self.__point(bfl)
        ],fill=image_piece.get_colour())

        # Right face
        if tfr['x'] < self.image_width/2:
            self.image_draw.polygon([
                self.__point(tbr),
                self.__point(bbr),
                self.__point(bfr),
                self.__point(tfr)
            ],fill=image_piece.get_colour())

        # Left face
        if tfl['x'] > self.image_width/2:
            self.image_draw.polygon([
                self.__point(tbl),
                self.__point(bbl),
                self.__point(bfl),
                self.__point(tfl)
            ],fill=image_piece.get_colour())

def transform_frame(frame_in, width_in, height_in):
    img_in = Image.fromarray(frame_in)
    img_out = Image.new('RGB', (width_in * OUTPUT_SCALE, height_in * OUTPUT_SCALE), IMAGE_BACKGROUND)

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
    [renderer.draw(piece) for piece in finished_queue]

    frame_out = np.asarray(img_out)

    return frame_out

def process(in_file, out_file):
    video_in = cv2.VideoCapture(in_file)
    fps = video_in.get(cv2.CAP_PROP_FPS)
    width_in = int(video_in.get(cv2.CAP_PROP_FRAME_WIDTH))
    height_in = int(video_in.get(cv2.CAP_PROP_FRAME_HEIGHT))

    video_out = cv2.VideoWriter(out_file, cv2.VideoWriter_fourcc(*'MP4V'), fps, (width_in * OUTPUT_SCALE, height_in * OUTPUT_SCALE))

    frame_count = 1
    while video_in.isOpened():
        frame_count += 1
        found_frame, frame_in = video_in.read()
        if found_frame:
            frame_out = transform_frame(frame_in, width_in, height_in)
            video_out.write(frame_out)
            print('Frame {}'.format(frame_count))
        else:
            break

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