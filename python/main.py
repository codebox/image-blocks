import sys, os.path, cv2
import numpy as np
from PIL import Image, ImageDraw

IMAGE_BACKGROUND = (255, 255, 255)
VARIANCE_THRESHOLD = 200
MIN_PIECE_SIZE = 5
OUTPUT_SCALE = 2

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
        if self.width <= MIN_PIECE_SIZE and self.height <= MIN_PIECE_SIZE:
            return 0

        min_v = 1000
        max_v = 0
        for x in range(self.x1, self.x2+1):
            for y in range(self.y1, self.y2+1):
                r,g,b = self.image_data[x,y]
                v = r + g + b
                min_v = min(min_v, v)
                max_v = max(max_v, v)

        return max_v - min_v

    def get_colour(self):
        r_total = g_total = b_total = count = 0

        for x in range(self.x1, self.x2+1):
            for y in range(self.y1, self.y2+1):
                r,g,b = self.image_data[x,y]
                r_total += r
                g_total += g
                b_total += b
                count += 1

        return int(r_total/count), int(g_total/count), int(b_total/count)

class ImagePieceBuilder:
    def __init__(self, image):
        self.image = image

    def build_piece(self, x1, y1, x2, y2):
        return ImagePiece(self.image, x1, y1, x2, y2)

class PieceRenderer:
    def __init__(self, image):
        self.image = image
        self.image_draw = ImageDraw.Draw(image)

    def __point(self, x, y):
        return x * OUTPUT_SCALE, y * OUTPUT_SCALE

    def draw(self, image_piece):
        x1 = image_piece.x1
        y1 = image_piece.y1
        x2 = image_piece.x2
        y2 = image_piece.y2

        self.image_draw.polygon([
            self.__point(x1, y1),
            self.__point(x2, y1),
            self.__point(x2, y2),
            self.__point(x1, y2)
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