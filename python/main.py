import sys, os.path, cv2
import numpy as np
from PIL import Image

IMAGE_BACKGROUND = (255, 255, 255)

def transform_frame(frame_in, size):
    img_in = Image.fromarray(frame_in)
    img_out = Image.new('RGB', size, IMAGE_BACKGROUND)

    frame_out = np.asarray(img_out)
    return frame_out

def process(in_file, out_file):
    video_in = cv2.VideoCapture(in_file)
    fps = video_in.get(cv2.CAP_PROP_FPS)
    width = int(video_in.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(video_in.get(cv2.CAP_PROP_FRAME_HEIGHT))

    video_out = cv2.VideoWriter(out_file, cv2.VideoWriter_fourcc(*'MP4V'), fps, (width, height))

    while video_in.isOpened():
        found_frame, frame_in = video_in.read()
        if found_frame:
            frame_out = transform_frame(frame_in, (width, height))
            video_out.write(frame_out)
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