from keras.models import load_model  # TensorFlow is required for Keras to work
import cv2  # Install opencv-python
import numpy as np
import paho.mqtt.client as mqtt
import tkinter as tk
import ttkbootstrap as ttk
from PIL import Image, ImageTk
import pathlib
import time
import json

############################
### READ JSON AND CONFIG ###
############################

f = open('setting.json')
 
# returns JSON object as
# a dictionary
setting_value = json.load(f)

##############
### CONFIG ###
##############

def config():
    global MQTT_SERVER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD, MQTT_TOPIC_PUB, MQTT_TOPIC_SUB, DEFAULT_IMG, CONFIDENCE_SCORE_CONFIRM, TIMES_CONFIRM
    # CONFIG MQTT
    MQTT_SERVER = "mqtt.ohstem.vn"
    MQTT_PORT = 1883
    MQTT_USERNAME = setting_value["mqttUsername"]
    MQTT_PASSWORD = setting_value["mqttPassword"]
    MQTT_TOPIC_PUB = MQTT_USERNAME + "/feeds/" + setting_value["defaultPublishFeed"]
    # MQTT_TOPIC_PUB2 = MQTT_USERNAME + "/feeds/V2"
    MQTT_TOPIC_SUB = MQTT_USERNAME + "/feeds/V3"

    # CONFIG DEFAULT IMAGE WHEN THE CAMERA IS NOT OPEN
    DEFAULT_IMG = Image.open("assets/bo.bmp")

    CONFIDENCE_SCORE_CONFIRM = np.float64(int(setting_value["confidenScoreConfirm"]))
    TIMES_CONFIRM = int(setting_value["timesConfirm"])

config()

root = tk.Tk()
root.title("Robot app")
root.resizable(False, False)
# root.geometry("600x600+150+150")
container = tk.Frame(root)
container.pack(padx=10, pady=10)

# Global variable
get_image_running = 0
send_MQTT_running = 0
cam = 0
ai_result = 0
count_ai = 0
count_ai_confirm = 0

arr_model = []
arr_model_name = []
arr_class_names = []
num_of_model_loaded = 0
model = 0
class_names = 0    

######################
### MODEL FUNCTION ###
######################

# Get list of models
model_list = []
get_model = pathlib.Path("models")
for item in get_model.iterdir():
    model_list.append(str(item)[7:])



# Auto load model bienbao when program start
def auto_load_model():
    global model, class_names, num_of_model_loaded
    autoLoadModel = setting_value["autoLoadModel"]
    # Load the model
    keras_path = "models/" + autoLoadModel + "/keras_Model.h5"
    class_names_path = "models/" + autoLoadModel + "/labels.txt"
    model = load_model(keras_path, compile=False)
    # Load the labels
    class_names = open(class_names_path, "r").readlines()
    arr_model.append(model)
    arr_model_name.append(autoLoadModel)
    arr_class_names.append(class_names)
    num_of_model_loaded += 1
    print("Auto load model " + autoLoadModel + " sucessful")
    message["text"] = "Auto load model " + autoLoadModel + " sucessful"

# Function load model
def my_load_model(model_choose):
    global model, class_names, num_of_model_loaded
    if get_image_running == 1:
        print("Stop camera before load model")
        message["text"] = "Stop camera before load model"
        return
    model_name = str(model_choose)
    for index, loaded_model in enumerate(arr_model_name):
        if loaded_model == model_name:
            model = arr_model[index]
            class_names = arr_class_names[index]
            num_of_model_loaded += 1
            print("Load model " + model_name + " sucessful")
            message["text"] = "Load model " + model_name + " sucessful"
            return

    # Keras path to load
    keras_path = "models/" + model_name + "/keras_Model.h5"
    # Class name path to load
    class_names_path = "models/" + model_name + "/labels.txt"
    # Check path exist
    keras_path_check = pathlib.Path(keras_path)
    class_names_path_check = pathlib.Path(class_names_path)
    if keras_path_check.exists() and class_names_path_check.exists():
        pass
    else:
        print("The path does not exist! Check your path!!\nLoad model fail")
        message["text"] = "The path does not exist! Check your path!!\nLoad model fail"
        return
    # Reload the model
    model = load_model(keras_path, compile=False)
    # Reload the labels
    class_names = open(class_names_path, "r").readlines()

    arr_model.append(model)
    arr_model_name.append(model_name)
    arr_class_names.append(class_names)
    num_of_model_loaded += 1
    print("Load model " + model_name + " sucessful")
    message["text"] = "Load model " + model_name + " sucessful"


###################################
### CAMERA AND PREDICT FUNCTION ###
###################################

# Update frame and prediction
def show_img():
    global cam, ai_result, count_ai, count_ai_confirm, AREA
    ret, frame = cam.read()  # type: ignore
    cv2_img = DEFAULT_IMG
    if get_image_running:
        cv2_img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
        cv2_img = Image.fromarray(cv2_img)
        width, height = cv2_img.size
        count_ai += 1

        if count_ai == 15:
            image = cv2.resize(frame, (224, 224), interpolation=cv2.INTER_AREA)

            # Make the image a numpy array and reshape it to the models input shape.
            image = np.asarray(image, dtype=np.float32).reshape(1, 224, 224, 3)

            # Normalize the image array
            image = (image / 127.5) - 1

            # Predicts the model
            prediction = model.predict(image)  # type: ignore
            index = np.argmax(prediction)
            class_name = class_names[index]  # type: ignore
            confidence_score = prediction[0][index]

            # Print prediction and confidence score
            print("Class:", class_name[2:], end="")
            print("Confidence Score:", str(np.round(confidence_score * 100))[:-2], "%")
            message["text"] = "Class:" + class_name[2:] + " Value:" + str(np.round(confidence_score * 100))[:-2] + "%"
            if send_MQTT_running:
                print("confirm running ...")
                if confidence_score * 100 > CONFIDENCE_SCORE_CONFIRM and class_name[2:] == ai_result:
                    count_ai_confirm += 1
                    if count_ai_confirm >= TIMES_CONFIRM:
                        print("#$%^&*()1234 GUI LEN MQTT FEED: " + MQTT_TOPIC_PUB + "#$%^&*()1234")
                        mqttClient.publish(MQTT_TOPIC_PUB, ai_result, 0, True)
                        count_ai_confirm = 0
                else:
                    count_ai_confirm = 0

            ai_result = class_name[2:]
            count_ai = 0

    cv2_img = cv2_img.resize((320, 240))
    cv2_img = ImageTk.PhotoImage(cv2_img)
    label_cv.config(image=cv2_img)
    label_cv.image = cv2_img  # type: ignore #VERY IMPORTANT

    if get_image_running:
        root.after(5, show_img)


# Show camera
def start_cam():
    global get_image_running, cam, num_of_model_loaded
    if num_of_model_loaded == 0:
        print("Load model before start camera")
        message["text"] = "Load model before start camera"
        return
    get_image_running = 1
    ##############
    ### CAM IP ###
    ##############
    # cam = cv2.VideoCapture("http://192.168.1.56:81/stream")
    cam = cv2.VideoCapture(0)
    show_img()


# Stop camera
def stop_cam():
    global get_image_running, cam, send_MQTT_running
    get_image_running = 0
    send_MQTT_running = 0
    cam.release()  # type: ignore
    cv2.destroyAllWindows()


#####################
### MQTT FUNCTION ###
#####################

def mqtt_connected(client, userdata, flags, rc):
    print("Connected succesfully!!")
    client.subscribe(MQTT_TOPIC_SUB)


def mqtt_subscribed(client, userdata, mid, granted_qos):
    print("Subscribed to Topic!!!")


mqttClient = mqtt.Client()
mqttClient.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
mqttClient.connect(MQTT_SERVER, int(MQTT_PORT), 60)

# Register mqtt events
mqttClient.on_connect = mqtt_connected
mqttClient.on_subscribe = mqtt_subscribed


# mqttClient.loop_start()

# while True:
#     # time.sleep(5)
#     ai_result = ai_detector()
#     if not ai_result:
#         break
#     print(ai_result)
#     mqttClient.publish(MQTT_TOPIC_PUB, ai_result, 0, True)

def send_to_MQTT(feed):
    if get_image_running == 0:
        print("START CAMERA BEFORE SEND")
        message["text"] = "START CAMERA BEFORE SEND"
        return
    global send_MQTT_running, MQTT_TOPIC_PUB
    MQTT_TOPIC_PUB = MQTT_USERNAME + "/feeds/" + feed
    send_MQTT_running = 1
    print("START SENDING TO MQTT")
    message["text"] = "START SENDING TO MQTT"
    # MQTT_loop()


# def MQTT_loop():
#     global ai_result, send_MQTT_running
#     mqttClient.publish(MQTT_TOPIC_PUB, ai_result, 0, True)
#     print("SEND TO MQTT")
#     if send_MQTT_running:
#         root.after(50, MQTT_loop)
#     else:
#         print("STOP SENDING TO MQTT")
#         message["text"] = "STOP SENDING TO MQTT"

def close_send_MQTT():
    global send_MQTT_running
    send_MQTT_running = 0

#####################
### Reset program ###
#####################

def reset_program():
    global get_image_running
    close_send_MQTT()
    if get_image_running == 1:
        stop_cam()
    config()

#################
### tkinter #####
#################

def setting_popup():
    global setting_value

    f = open('setting.json')
    setting_value = json.load(f)

    setting_window = tk.Toplevel(root)
    setting_window.title("Setting")

    number_of_var = len(setting_value)
    variable_frame = [tk.Frame(setting_window) for i in range(number_of_var)]
    setting_key = list(setting_value.keys())
    var = [tk.StringVar() for i in range(number_of_var)]
    for i in range(number_of_var):
        variable_frame[i].grid(row=i, column=0, pady=5)
        variable_label = ttk.Label(variable_frame[i], text=setting_key[i], width=25)
        variable_label.pack(side="left", fill="both", padx=(15, 0))
        var[i].set(setting_value[setting_key[i]])
        variable_value = tk.Entry(variable_frame[i], textvariable=var[i], width=15)
        variable_value.pack(side="left", fill="both", padx=(0, 15))

    def change_setting():
        for i in range(number_of_var):
            setting_value[setting_key[i]] = var[i].get()

        # Modify json file
        with open("setting.json", "w") as outfile:
            json.dump(setting_value, outfile)

        reset_program()
        setting_window.destroy()

    button_save = ttk.Button(setting_window, text="Save", width=15, command=change_setting)
    button_save.grid(row=number_of_var, column=0, pady=10)
    
### Menu bar ###

# create a menubar
menubar = ttk.Menu(root)
root.config(menu=menubar)

# create the file_menu
file_menu = ttk.Menu(menubar, tearoff=False)

# add menu items to the File menu
file_menu.add_command(label='New', command=lambda: print("New"))
file_menu.add_command(label='Open', command=lambda: print("Open"))
file_menu.add_command(label='Close', command=lambda: print("Close"))
# file_menu.add_separator()

# add a submenu
sub_menu = ttk.Menu(file_menu, tearoff=False)
sub_menu.add_command(label='Keyboard Shortcuts')
sub_menu.add_command(label='Color Themes')

# add the File menu to the menubar
file_menu.add_cascade(label="Preferences", menu=sub_menu)

# add Exit menu item
file_menu.add_separator()
file_menu.add_command(label='Exit', command=root.destroy)

menubar.add_cascade(label="File", menu=file_menu, underline=0)
# create the Help menu
setting_menu = ttk.Menu(menubar, tearoff=False)

setting_menu.add_command(label='Setting', command=setting_popup)

# add the Help menu to the menubar
menubar.add_cascade(label="Setting", menu=setting_menu, underline=0)

### Main screen ###
main_screen = ttk.Frame(container)
main_screen.grid(row=0, column=0, padx=(0, 20))

main_screen_label = ttk.Label(main_screen, text="MAIN SCREEN", font=("Arial", 20))
main_screen_label.grid(row=0, column=0, pady=(0, 10))

button_frame = tk.Frame(main_screen)
button_frame.grid(row=1, column=0, pady=(0, 10))

cv2_img = DEFAULT_IMG.resize((320, 240))
cv2_img = ImageTk.PhotoImage(cv2_img)
label_cv = ttk.Label(main_screen, image=cv2_img)
label_cv.grid(row=2, column=0, pady=(0, 10))

# Show massage
message = ttk.Label(main_screen, text="Message: ......", font=("Arial", 12))
message.grid(row=3, column=0)

# chuphinh = ttk.Button(main_screen, text="Chup hinh")
# chuphinh.grid(row=0, column=0)

### Model button ###
# Choose model
button_model_frame = ttk.Labelframe(button_frame, text="Models", padding=5)
button_model_frame.grid(row=0, column=0, padx=(0, 10))

model_choose = tk.StringVar()
option_menu = ttk.OptionMenu(
    button_model_frame,
    model_choose,
    "Not selected",
    *model_list,
    bootstyle="secondary"  # type: ignore
)
option_menu.pack(side="top", fill="both", pady=(0, 10))

# Button to load model
button_load_model = ttk.Button(button_model_frame, text="Load Model", command=lambda: my_load_model(model_choose.get()))
button_load_model.pack(side="top", fill="both")
#####

### Camera button ###
button_cam_frame = ttk.Labelframe(button_frame, text="Camera", padding=5)
button_cam_frame.grid(row=0, column=1, padx=(0, 10))

button_start_cam = ttk.Button(
    button_cam_frame,
    text="Start camera",
    bootstyle="success",  # type: ignore
    command=start_cam
)
button_start_cam.pack(side="top", fill="both", pady=(0, 10))

button_stop_cam = ttk.Button(
    button_cam_frame,
    text="Stop camera",
    bootstyle="danger",  # type: ignore
    command=stop_cam
)
button_stop_cam.pack(side="top", fill="both")
#####

### MQTT button ###
button_MQTT_frame = ttk.Labelframe(button_frame, text="MQTT", padding=5)
button_MQTT_frame.grid(row=0, column=2)

feed_list = []
default_feed = setting_value["defaultPublishFeed"]
for i in range(20):
    feed_list.append("V" + str(i + 1))
feed_choose = tk.StringVar()
option_menu = ttk.OptionMenu(
    button_MQTT_frame,
    feed_choose,
    default_feed,
    *feed_list,
)
option_menu.pack(side="top", fill="both", pady=(0, 10))

button_send_to_MQTT = ttk.Button(button_MQTT_frame, text="Send to MQTT", command=lambda: send_to_MQTT(feed_choose.get()))
button_send_to_MQTT.pack(side="top", fill="both", pady=(0, 10))

button_close_send_MQTT = ttk.Button(
    button_MQTT_frame, 
    text="Close send", 
    bootstyle="danger",  # type: ignore
    command=close_send_MQTT
)
button_close_send_MQTT.pack(side="top", fill="both")
#####

### Terminal screen ###
# terminal_screen = tk.Frame(container)
# terminal_screen.grid(row=0, column=1)

# terminal_screen_label = ttk.Label(terminal_screen, text="TERMINAL" , font=("Arial", 20))
# terminal_screen_label.grid(row=0, column=0, pady=(0, 10))

# terminal_screen_text = ttk.Frame(terminal_screen)
# terminal_screen_text.grid(row=1, column=0, pady=(0, 10))

# text = ttk.LabelFrame(terminal_screen_text, text="Output")
# text.pack()
#####

# auto_load_model()

root.mainloop()
