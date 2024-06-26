
import argparse
import io
from PIL import Image
import datetime

import torch
import cv2
import numpy as np
from re import DEBUG, sub
from flask import Flask, render_template, request, redirect, send_file, url_for, Response
from werkzeug.utils import secure_filename, send_from_directory
import os
import subprocess
from subprocess import Popen
import re
import requests
import shutil
import time
from threading import Thread
import glob


from ultralytics import YOLO


app = Flask(__name__)
global capture,rec_frame, switch, rec, out 
capture=0
switch=1
rec=0

try:
    os.mkdir('./shots')
except OSError as error:
    pass

camera = cv2.VideoCapture(0)

def record(out):
    global rec_frame
    while(rec):
        time.sleep(0.05)
        out.write(rec_frame)

@app.route("/")
def hello_world():
    # return render_template("index.html")
    if "image_path" in request.args:
        image_path = request.args["image_path"]
        return render_template("index.html", image_path=image_path)
    return render_template("index.html")

    
@app.route("/", methods=["GET", "POST"])
def predict_img():
    if request.method == "POST":
        if 'file' in request.files:
            f = request.files['file']
            basepath = os.path.dirname(__file__)
            filepath = os.path.join(basepath,'uploads',f.filename)
            print("upload folder is ", filepath)
            f.save(filepath)
            global imgpath
            predict_img.imgpath = f.filename
            print("printing predict_img :::::: ", predict_img)
                                               
            file_extension = f.filename.rsplit('.', 1)[1].lower() 
            
            if file_extension == 'jpg':
                # Handle image upload
                img = cv2.imread(filepath)

                # Perform the detection
                model = YOLO('best.pt')
                detections = model(img, save=True)

                # Find the latest subdirectory in the 'runs/detect' folder
                folder_path = os.path.join(basepath, 'runs', 'detect')
                subfolders = [f for f in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, f))]
                latest_subfolder = max(subfolders, key=lambda x: os.path.getctime(os.path.join(folder_path, x)))

                # Construct the relative path to the detected image file
                static_folder = os.path.join(basepath, 'static', 'assets')
                relative_image_path = os.path.relpath(os.path.join(folder_path, latest_subfolder, f.filename), static_folder)
                image_path = os.path.join(folder_path, latest_subfolder, f.filename)
                print("Relative image path:", relative_image_path)  # Print the relative_image_path for debugging
                
                return render_template('index.html', image_path=relative_image_path, media_type='image')

            elif file_extension == 'mp4':
                
                # Handle video upload
                video_path = filepath  # replace with your video path
                cap = cv2.VideoCapture(video_path)

                # get video dimensions
                frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

                # Define the codec and create VideoWriter object
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                out = cv2.VideoWriter(
                    "output.mp4", fourcc, 30.0, (frame_width, frame_height)
                )

                # initialize the YOLOv8 model here
                model = YOLO("best.pt")

                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break

                    # do YOLOv9 detection on the frame here
                    # model = YOLO('yolov9c.pt')
                    results = model(frame, save=True)  # working
                    print(results)
                    cv2.waitKey(1)

                    res_plotted = results[0].plot()
                    cv2.imshow("result", res_plotted)

                    # write the frame to the output video
                    out.write(res_plotted)

                    if cv2.waitKey(1) == ord("q"):
                        break

                return render_template('index.html', video_path='output.mp4', media_type='video')

    # If no file uploaded or GET request, return the template with default values
    return render_template("index.html", image_path="", media_type='image')



# #The display function is used to serve the image or video from the folder_path directory.
@app.route('/<path:filename>')
def display(filename):
    folder_path = 'runs/detect'
    subfolders = [f for f in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, f))]    
    latest_subfolder = max(subfolders, key=lambda x: os.path.getctime(os.path.join(folder_path, x)))    
    directory = os.path.join(folder_path, latest_subfolder)  
    print("printing directory: ",directory) 
    files = os.listdir(directory)
    latest_file = files[0]
    
    print(latest_file)

    image_path = os.path.join(directory, latest_file)

    file_extension = latest_file.rsplit(".", 1)[1].lower()

    if file_extension == "jpg":
        return send_file(image_path, mimetype="image/jpeg")
    elif file_extension == "mp4":
        return send_file(image_path, mimetype="video/mp4")
    else:
        return "Invalid file format"
        
def get_frame():
    folder_path = os.getcwd()
    mp4_files = 'output.mp4'
    video = cv2.VideoCapture(mp4_files)  # detected video path
    while True:
        success, frame = video.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode(".jpg", frame)
            frame = buffer.tobytes()
      
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')   
        time.sleep(0.1)  #control the frame rate to display one frame every 100 milliseconds: 

# function to display the detected objects video on html page
@app.route("/video_feed")
def video_feed():
    print("function called")

    return Response(get_frame(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')
        
def gen_frames():  # generate frame by frame from camera
    global out, capture,rec_frame
    model = YOLO("best.pt")
    while True:
        success, frame = camera.read()
        if success:
            if(capture):
                capture=0
                now = datetime.datetime.now()
                p = os.path.sep.join(['shots', "shot_{}.png".format(str(now).replace(":",''))])
                cv2.imwrite(p, frame)
            
            if(rec):
                rec_frame=frame
                frame= cv2.putText(cv2.flip(frame,1),"Recording...", (0,25), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255),4)
                frame=cv2.flip(frame,1)
            
                
            try:
                # Perform object detection on the frame
                img = Image.fromarray(frame)
                model = YOLO("best.pt")
                results = model(img, save=True)

                # Plot the detected objects on the frame
                res_plotted = results[0].plot()
                img_BGR = cv2.cvtColor(res_plotted, cv2.COLOR_BGR2RGB)

                # Convert the frame to JPEG format for streaming
                ret, buffer = cv2.imencode(".jpg", img_BGR)
                frame = buffer.tobytes()

                yield (
                    b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n\r\n"
                )
            except Exception as e:
                pass
                
        else:
            pass

@app.route("/webcam_feed")
def webcam_feed():
    return Response(gen_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route('/requests',methods=['POST','GET'])
def tasks():
    global switch,camera
    if request.method == 'POST':
        if request.form.get('click') == 'Capture':
            global capture
            capture=1 
        elif  request.form.get('start') == 'Stop/Start':
            
            if(switch==0):
                camera = cv2.VideoCapture(0)
                switch=1                
            else:
                switch=0
                camera.release()
                cv2.destroyAllWindows()
                
        elif  request.form.get('rec') == 'Start/Stop Recording':
            global rec, out
            rec= not rec
            if(rec):
                now=datetime.datetime.now() 
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                out = cv2.VideoWriter('vid_{}.avi'.format(str(now).replace(":",'')), fourcc, 20.0, (640, 480))
                #Start new thread for recording the video
                thread = Thread(target = record, args=[out,])
                thread.start()
            elif(rec==False):
                out.release()
                          
                 
    elif request.method=='GET':
        return render_template('index.html')
    return render_template('index.html')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flask app exposing yolov9 models")
    parser.add_argument("--port", default=5000, type=int, help="port number")
    args = parser.parse_args()
    model = YOLO('best.pt')
    app.run(host="0.0.0.0", port=args.port) 
