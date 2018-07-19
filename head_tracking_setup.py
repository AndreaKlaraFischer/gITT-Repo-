#!/usr/bin/python3
# -*- coding: utf-8 -*-

import sys
import wiimote

from PyQt5.QtWidgets import QWidget, QApplication
from PyQt5.QtGui import QPainter, QColor
from PyQt5.QtCore import QRect

"""
    This script allows you to test the head tracking.
    
    The aspect ratio of the Window is equal to the asprect ratio of the Wiimote. 
    
    The green Point marks the center of the Wiimote IR Camera.
    The two red points mark the positions of the two leds of the Head-Tracking-Glasses
    
    The blue point marks the middle point of the Head-Tracking-Glasses.
    We use that point for the player pos.


"""

WIIMOTE_ADDRESS = "B8:AE:6E:55:B5:0F"

class HeadTrackingSetup(QWidget):

    def __init__(self):
        super().__init__()

        self.WIIMOTE_IR_CAM_WIDTH = 1024
        self.WIIMOTE_IR_CAM_HEIGHT = 768
        self.WIIMOTE_IR_CAM_CENTER = (self.WIIMOTE_IR_CAM_WIDTH/2, self.WIIMOTE_IR_CAM_HEIGHT/2)

        self.left = (0,0)
        self.right = (0,0)
        self.center = (0,0)

        self.connect_wiimote()
        self.initUI()

    def initUI(self):
        self.setGeometry(300, 0, self.WIIMOTE_IR_CAM_WIDTH, self.WIIMOTE_IR_CAM_HEIGHT)
        self.setWindowTitle('Head Tracking Setup')
        self.show()

    def connect_wiimote(self):
        addr = WIIMOTE_ADDRESS
        name = None
        print(("Connecting to %s (%s)" % (name, addr)))
        wm = wiimote.connect(addr, name)
        wm.ir.register_callback(self.get_ir_data)

    def get_ir_data(self, ir_data):
        if len(ir_data) == 2:
            left = (ir_data[0]["x"], ir_data[0]["y"])
            right = (ir_data[1]["x"], ir_data[1]["y"])
            self.invert_points(left, right)
            self.calculate_head_center()
            self.update()

    def invert_points(self, left, right):
        self.left = (self.WIIMOTE_IR_CAM_WIDTH - left[0], self.WIIMOTE_IR_CAM_HEIGHT - left[1])
        self.right = (self.WIIMOTE_IR_CAM_WIDTH - right[0], self.WIIMOTE_IR_CAM_HEIGHT - right[1])

    def calculate_head_center(self):
        self.center = ((self.left[0] + self.right[0]) / 2,(self.left[1] + self.right[1]) / 2)

    def to_screen_coordinates(self, screen_width, screen_height):
        x_on_screen = (self.center[0] / self.WIIMOTE_IR_CAM_WIDTH) * screen_width
        y_on_screen = (self.center[1] / self.WIIMOTE_IR_CAM_HEIGHT) * screen_height
        return x_on_screen, y_on_screen

    def paintEvent(self, e):
        qp = QPainter()
        qp.begin(self)
        self.drawPoints(qp)
        qp.end()

    def drawPoints(self, qp):
        # Left and right IR LEDs
        qp.setBrush(QColor(255, 0, 0))
        a = QRect(self.left[0], self.left[1], 20, 20)
        b = QRect(self.right[0], self.right[1], 20, 20)
        qp.drawRect(a)
        qp.drawRect(b)

        # Middle point between two LEDs
        qp.setBrush(QColor(0, 0, 255))
        qp.drawRect(self.center[0], self.center[1], 20, 20)

        qp.setBrush(QColor(0, 255, 0))
        qp.drawRect(self.WIIMOTE_IR_CAM_CENTER[0], self.WIIMOTE_IR_CAM_CENTER[1], 20, 20)


if __name__ == '__main__':

    app = QApplication(sys.argv)
    ex = HeadTrackingSetup()
    sys.exit(app.exec_())
