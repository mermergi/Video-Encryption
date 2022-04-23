import cv2
import os
import time
from PIL import Image
from ffmpy import FFmpeg
import string
import sys 
sys.path.append(os.path.join(os.path.split(os.path.realpath(__file__))[0]+'\\Config'))
from config import global_config


def img2Vedio(imgPath, videoPath):

    images = os.listdir(imgPath)
    images.sort(key=lambda x: int(x[:-4]))
    fps = 10
    fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    im = Image.open(imgPath + images[0])
    videoWriter = cv2.VideoWriter(videoPath, fourcc, fps, im.size,isColor=True)
    for im_name in range(len(images)):
        print("Video is assembled by Image, Current Loop is :",images[im_name])
        frame = cv2.imread(imgPath + images[im_name])
        videoWriter.write(frame)
    videoWriter.release()

def avi2Mp4(videoPath, outVideoPath):
    capture = cv2.VideoCapture(videoPath)
    fps = capture.get(cv2.CAP_PROP_FPS)
    size = (int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)), int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    suc = capture.isOpened()

    allFrame = []
    while suc:
        suc, frame = capture.read()
        if suc:
            allFrame.append(frame)
    capture.release()

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    videoWriter = cv2.VideoWriter(outVideoPath, fourcc, fps, size)
    for aFrame in allFrame:
        videoWriter.write(aFrame)
    videoWriter.release()

if __name__ == '__main__':
    print("openCVImg2VedioScript execute Start !")
    imgPath = global_config.getRaw('config', 'IMG_PATH')
    inputVideoPath = global_config.getRaw('config', 'IMG_VIDEO_PATH')
    inputVideoName = global_config.getRaw('config', 'IMG_VIDEO_PATH')+'/0422Result.avi'
    img2Vedio(imgPath, inputVideoName)
    outVideoPath = inputVideoPath+'/0422Result.mp4'
    avi2Mp4(inputVideoName, outVideoPath)
    os.remove(inputVideoName)
    print("openCVImg2VedioScript execute End !")
