import cv2
import os
import string
import sys 
sys.path.append(os.path.join(os.path.split(os.path.realpath(__file__))[0]+'\\Config'))
from config import global_config

def delFile(path):
    ls = os.listdir(path)
    for i in ls:
        c_path = os.path.join(path, i)
        if os.path.isdir(c_path):
            del_file(c_path)
        else:
            os.remove(c_path)

if __name__ == '__main__':
    print("openCVVedio2ImgScript execute Start !")
    videoPath = global_config.getRaw('config', 'VIDEO_PATH')
    cap = cv2.VideoCapture(videoPath)
    savePath = global_config.getRaw('config', 'SAVE_PATH')
    ImgNums=480
    if os.path.exists(savePath):
        delFile(savePath) 
    else:
        os.makedirs(savePath)
    imgPath = ""
    sum = cap.get(7)
    
    time = (int)(sum / ImgNums)
    sum = 0
    i = 0
    while True:
        print("Image cut by video, Current Loop is :",i)
        ret, frame = cap.read()
        if ret == False:
            break
        sum += 1
        if sum % time == 0 and i < ImgNums:
            i += 1
            imgPath = "VideoCut4Img/%s.jpg" % str(i)
            cv2.imwrite(imgPath, frame)
     
    print("openCVVedio2ImgScript execute End !")