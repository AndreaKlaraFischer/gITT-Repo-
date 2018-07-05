#!/usr/bin/env python3

import wiimote
import time
import sys
import pygame
import os
from PyQt5 import QtWidgets, QtCore, uic

class WiimoteGame(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self.loop_timer = QtCore.QTimer()
        self.initUI()
        self.init_pygame()
        self.connect_wiimotes()

    # Init the Window
    def initUI(self):
        layout = QtWidgets.QVBoxLayout()
        layoutSettings = QtWidgets.QHBoxLayout()
        layoutAdded = QtWidgets.QHBoxLayout()
        self.setWindowTitle("ITT Final Project")

        self.showGestures = QtWidgets.QLabel("")
        layoutAdded.addWidget(self.showGestures)
        self.labelRecognize = QtWidgets.QLabel("")
        layoutAdded.addWidget(self.labelRecognize)
        self.labelRecognize.setAlignment(QtCore.Qt.AlignRight)
        layout.setAlignment(QtCore.Qt.AlignBottom)
        layoutAdded.setAlignment(QtCore.Qt.AlignBottom)
        layout.addLayout(layoutSettings)
        layout.addLayout(layoutAdded)
        self.window().setLayout(layout)
        self.show()

    # Prepare the audio files
    def init_pygame(self):
        pygame.init()
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

    # Show hints on the UI explaining which button causes which sound
    def set_button_labels(self, label_up, label_down, label_left, label_right):
        self.ui.button_up.setText(label_up)
        self.ui.button_down.setText(label_down)
        self.ui.button_left.setText(label_left)
        self.ui.button_right.setText(label_right)

    # Starting the game loop
    def start_loop(self):
        self.wm.speaker.beep()
        self.loop_timer.setSingleShot(False)
        self.loop_timer.timeout.connect(self.loop_iteration)
        self.loop_timer.start(50)

    # One iteration of the loop. Check wiimote rotation, update ui, check for button presses.
    def loop_iteration(self):
        print("A: " + str(self.wm_pointer.accelerometer[1]))
        print("B: " + str(self.wm_tracker.accelerometer[1]))


def main():
    app = QtWidgets.QApplication(sys.argv)
    wiimote_game = WiimoteGame()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
