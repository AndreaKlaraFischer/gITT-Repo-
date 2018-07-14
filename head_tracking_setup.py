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
    
    Todo: Pause if Glasses not visible
    Todo: Filter out "Jumps" of cursor

"""


class HeadTrackingSetup(QWidget):

    def __init__(self):
        super().__init__()

        self.WIIMOTE_IR_CAM_WIDTH = 1024
        self.WIIMOTE_IR_CAM_HEIGHT = 768

        self.left = (0,0)
        self.right = (0,0)
        self.WIIMOTE_IR_CAM_CENTER = (self.WIIMOTE_IR_CAM_WIDTH/2, self.WIIMOTE_IR_CAM_HEIGHT/2)

        self.connect_wiimote()
        self.initUI()

    def initUI(self):
        self.setGeometry(300, 0, self.WIIMOTE_IR_CAM_WIDTH, self.WIIMOTE_IR_CAM_HEIGHT)
        self.setWindowTitle('Head Tracking Setup')
        self.show()

    def connect_wiimote(self):
        if len(sys.argv) == 1:
            print(wiimote.find())
            addr, name = wiimote.find()[0]
        elif len(sys.argv) == 2:
            addr = sys.argv[1]
            name = None

        print(("Connecting to %s (%s)" % (name, addr)))
        wm = wiimote.connect(addr, name)
        wm.ir.register_callback(self.print_ir)

    def print_ir(self, ir_data):
        if len(ir_data) == 2:
            self.left = (ir_data[0]["x"], ir_data[0]["y"])
            self.right = (ir_data[1]["x"], ir_data[1]["y"])
            self.invert_points()
            self.update()

    def invert_points(self):
        self.left = (self.WIIMOTE_IR_CAM_WIDTH - self.left[0], self.WIIMOTE_IR_CAM_HEIGHT - self.left[1])
        self.right = (self.WIIMOTE_IR_CAM_WIDTH - self.right[0], self.WIIMOTE_IR_CAM_HEIGHT - self.right[1])

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
        middle = ((self.left[0] + self.right[0])/2,(self.left[1] + self.right[1])/2)
        qp.setBrush(QColor(0, 0, 255))
        qp.drawRect(middle[0], middle[1], 20, 20)

        qp.setBrush(QColor(0, 255, 0))
        qp.drawRect(self.WIIMOTE_IR_CAM_CENTER[0], self.WIIMOTE_IR_CAM_CENTER[1], 20, 20)


if __name__ == '__main__':

    app = QApplication(sys.argv)
    ex = HeadTrackingSetup()
    sys.exit(app.exec_())
