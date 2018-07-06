#!/usr/bin/env python3

import glob
import sys
import pygame
import wiimote
from PyQt5 import QtWidgets, QtCore, QtGui
import numpy as np
from scipy import fft
from sklearn import svm


class WiimoteGame(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self.loop_timer = QtCore.QTimer()
        self.init_pygame()
        self.connect_wiimotes()



    # Prepare the audio files
    def init_pygame(self):
        pygame.init()
        self.screen = pygame.display.set_mode((500,500))
        pygame.display.set_caption('ITT Final Project')
        self.background = pygame.Surface(self.screen.get_size())
        self.background = self.background.convert()
        self.background.fill((250,250,250))
        font = pygame.font.Font(None, 36)
        self.text = font.render("Hello", 1, (10,10,10))
        textpos = self.text.get_rect()
        textpos.centerx = self.background.get_rect().centerx
        self.background.blit(self.text, textpos)
        self.screen.blit(self.background, (0,0))
        pygame.display.flip()
        try:
            # Init Sounds here (the soundfiles need to be in folder "assets"
            #pygame.mixer.music.load(os.path.join("assets", "instrumental.wav"))
            print("test")
        except pygame.error:
            print("Missing audio file!")
            sys.exit()

    # Start the pairing process, like in wiimote_demo.py
    def connect_wiimotes(self):
        if len(sys.argv) == 3:
            tracker = sys.argv[1]
            pointer = sys.argv[2]
            name_tracker = None
            name_pointer = None
            self.wm_tracker = wiimote.connect(tracker, name_tracker)
            self.wm_pointer = wiimote.connect(pointer, name_pointer)
            self.wm = self.wm_pointer

            # As soon as the Wiimote is connected, start the loop
            self.start_loop()
        else:
            print("Need two Mac Adresses")
            sys.exit()

    # Play a sound saved in the vocals dictionary
    def play_sound(self, vocal_name):
        sound = self.vocals[vocal_name]
        sound.play()



    # Starting the game loop
    def start_loop(self):
        self.wm_pointer.speaker.beep()
        self.game_mode = "shoot"
        self.prediction_values = [[], [], []]
        self.last_prediction = "Waiting for data..."
        self.category_list = []
        self.munition_counter = 20
        self.new_training_values = [[], [], []]
        self.prediction_values = [[], [], []]
        self.c = svm.SVC()
        self.minlen = 100000  # Just a large value to begin with
        self.qp = QtGui.QPainter()
        self.loop_timer.setSingleShot(False)
        self.loop_timer.timeout.connect(self.loop_iteration)
        self.loop_timer.start(35)



    # One iteration of the loop. Check wiimote rotation, update ui, check for button presses.
    def loop_iteration(self):
        #print("A: " + str(self.wm_pointer.accelerometer[1]))
        #print("B: " + str(self.wm_tracker.accelerometer[1]))

        # todo: handle enemies: every few ticks they will shoot based on their location


        # handles drawing mode and disables shooting while drawing
        if self.wm_pointer.buttons['A']:
            self.game_mode = "draw"
            # todo: draw a shield on the screen --> limit size and duration
        else:
            self.game_mode = "shoot"
            # disables drawing when shooted
            if self.wm_pointer.buttons['B']:
                # if munition available, allow shooting
                if self.munition_counter > 0:
                    self.munition_counter -= 1
                else:
                    print("shooting not possible, reloading necessary")
            # todo: track enemy position
            # todo: track pointer position

        # todo: add check for shields
        # todo: check for collision and handle lives etc.
        self.recognize_activity(self.wm_pointer.accelerometer)


        # necessary for closing the window in pygame
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()

    def recognize_activity(self, accelerometer):
        x_acc = accelerometer[0]
        y_acc = accelerometer[1]
        z_acc = accelerometer[2]
        #print(x_acc,y_acc,z_acc)

        # todo: if available, recognizing should be started, and if not add training data with gesture name
        # checks for available training data.
        self.read_data_from_csv()
        self.predicted_activity = self.predict_activity(x_acc,y_acc,z_acc)
        self.updateMunitionDisplay()

    def updateMunitionDisplay(self):
        self.background.fill((250, 250, 250))
        font = pygame.font.Font(None, 36)
        self.text = font.render(
            "Gesture: " + self.predicted_activity + " Munition: " + str(self.munition_counter) + "/20", 1, (10, 10, 10))
        textpos = self.text.get_rect()
        textpos.centerx = self.background.get_rect().centerx
        self.background.blit(self.text, textpos)
        self.screen.blit(self.background, (0, 0))

        if self.predicted_activity == "reload":
            if self.munition_counter != 20:
                self.munition_counter = 20

        pygame.display.flip()

    def get_categories(self):
        csv_files = glob.glob("*.csv")  # get all csv files from the directory
        for file in csv_files:
            # split file at _ character, so that only the name without id is returned
            categoryArr = file.split("_")
            # check if csv file is valid, i.e. contains a _
            if len(categoryArr) == 2:
                # if gesture is not already in the list that should represent the items in the dropdown menu,
                # add gesture to dropdown list
                if categoryArr[0] not in self.category_list:
                    self.category_list.append(categoryArr[0])
        return self.category_list


    # Parts of the code taken from the "Wiimote - FFT - SVM" notebook from Grips
    def read_data_from_csv(self):
        activities = {}
        categories = self.get_categories()
        if len(categories) == 0:
            print("No Categories created! Training not possible")
            return
        if len(categories) < 2:
            print("Not enough categories created to train")
            return

        for category in categories:
            activities[category] = []

        csv_files = glob.glob("*.csv")
        if len(csv_files) == 0:
            print("No CSV Files to train with!")
            return

        for csv_file in csv_files:
            category_name = csv_file.split("_")[0]
            for activity_name, value in activities.items():
                if activity_name == category_name:
                    activities[activity_name].append([])
                    for line in open(csv_file, "r").readlines():
                        x, y, z = map(int, line.strip().split(","))
                        mean = (x + y + z) / 3
                        activities[activity_name][len(activities[activity_name]) - 1].append(mean)

        self.cut_off_data(activities)

    def cut_off_data(self, activities):
        self.minlen = 10000000  # Large number to begin
        for activity_name, value in activities.items():
            for data in value:
                num_measurements = len(data)
                if num_measurements < self.minlen:
                    self.minlen = num_measurements

        for activity_name, value in activities.items():
            current = activities[activity_name]
            activities[activity_name] = [l[:self.minlen] for l in current]

        self.convert_to_frequency(activities)

    def convert_to_frequency(self, activities):

        for activity_name, value in activities.items():
            # This line is taken from the "Wiimote - FFT - SVM" notebook from Grips
            temp = [np.abs(fft(l) / len(l))[1:len(l) // 2] for l in value]
            activities[activity_name] = temp

        self.train(activities)

    def train(self, activities):
        categories = []
        training_data = []

        for activity_name, value in activities.items():
            for i in range(len(value)):
                categories.append(activity_name)
                training_data.append(value[i])

        self.c.fit(training_data, categories)

    def predict_activity(self, x, y, z):

        if len(self.prediction_values[0]) < self.minlen:
            self.prediction_values[0].append(x)
            self.prediction_values[1].append(y)
            self.prediction_values[2].append(z)
            return self.last_prediction
        else:
            #print(str(self.minlen) + " Values collected:")
            #print(len(self.prediction_values[0]))
            avg = []
            for i in range(len(self.prediction_values[0])):
                avg.append((self.prediction_values[0][i] + self.prediction_values[1][i] +
                            self.prediction_values[2][i]) / 3)

            self.prediction_values = [[], [], []]

            # This line is taken from the "Wiimote - FFT - SVM" notebook from Grips
            freq = [np.abs(fft(avg) / len(avg))[1:len(avg) // 2]]
            self.last_prediction = str(self.c.predict(freq)[0])
            return self.last_prediction


def main():
    app = QtWidgets.QApplication(sys.argv)
    wiimote_game = WiimoteGame()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
