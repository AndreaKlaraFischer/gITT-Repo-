#!/usr/bin/env python3

import glob
import sys
import pygame
import wiimote
from PyQt5 import QtWidgets, QtCore, QtGui
import numpy as np
from scipy import fft
from sklearn import svm

# from http://kidscancode.org/blog/2016/08/pygame_1-2_working-with-sprites/
class Enemy(pygame.sprite.Sprite):
    def __init__(self,all_sprites):
        # todo: create global constants for width and height
        pygame.sprite.Sprite.__init__(self)
        self.all_sprites = all_sprites

        self.image = pygame.Surface((50, 50))
        self.image.fill((250,0,0))
        self.rect = self.image.get_rect()
        self.rect.center = (10, 100)

    def update(self):
        self.rect.x += 2

    def shoot(self):
        bullet = Bullet(self.rect.centerx, self.rect.bottom, 10)
        self.all_sprites.add(bullet)
        # bullets.add(bullet)

# from http://kidscancode.org/blog/2016/08/pygame_shmup_part_1/
class Player(pygame.sprite.Sprite):
    def __init__(self, all_sprites):
        pygame.sprite.Sprite.__init__(self)
        self.all_sprites = all_sprites
        self.image = pygame.Surface((50, 40))
        self.image.fill((0,250,0))
        self.rect = self.image.get_rect()
        self.rect.centerx = 500 / 2
        self.rect.bottom = 500 - 100
        self.speedx = 0

    def update(self):
        self.speedx = 0
        # at the moment the movement of the player is handled via left and right arrows
        keystate = pygame.key.get_pressed()
        if keystate[pygame.K_LEFT]:
            self.speedx = -8
        if keystate[pygame.K_RIGHT]:
            self.speedx = 8
        self.rect.x += self.speedx
        # prevents the player to get outside of the screen
        if self.rect.right > 500:
            # todo: set to pause mode
            self.rect.right = 500
        if self.rect.left < 0:
            # todo: set to pause mode
            self.rect.left = 0

    def shoot(self):
        bullet = Bullet(self.rect.centerx, self.rect.top, -10)
        self.all_sprites.add(bullet)
        #bullets.add(bullet)

# from http://kidscancode.org/blog/2016/08/pygame_shmup_part_3/
class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, speed):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface((10, 20))
        self.image.fill((0,0,250))
        self.rect = self.image.get_rect()
        self.rect.bottom = y
        self.rect.centerx = x
        self.speedy = speed

    def update(self):
        self.rect.y += self.speedy
        # kill if it moves off the top of the screen
        if self.rect.bottom < 0:
            self.kill()

class WiimoteGame(QtWidgets.QWidget):

    def __init__(self,all_sprites):
        super().__init__()
        self.all_sprites = all_sprites

        self.loop_timer = QtCore.QTimer()
        self.init_pygame()
        self.connect_wiimotes()



    # Prepare the audio files
    def init_pygame(self):
        pygame.init()

        self.screen = pygame.display.set_mode((500,500))
        pygame.display.set_caption('ITT Final Project')

        self.drawInfoLine("Waiting for gesture ... ")
        self.drawGameCanvas()
        self.drawMunitionLine("20/20")

        # adds an enemy to the canvas. A sprite group is able to hold multiple sprites, i.e. enemies
        self.enemy = Enemy(self.all_sprites)
        self.all_sprites.add(self.enemy)

        self.player = Player(self.all_sprites)
        self.all_sprites.add(self.player)

        self.all_sprites.draw(self.screen)


        # updates complete pygame display
        pygame.display.flip()
        try:
            # Init Sounds here (the soundfiles need to be in folder "assets"
            #pygame.mixer.music.load(os.path.join("assets", "instrumental.wav"))
            print("test")
        except pygame.error:
            print("Missing audio file!")
            sys.exit()

    def drawInfoLine(self,text):
        self.info_line_top = pygame.Surface((500, 50))
        self.info_line_top = self.info_line_top.convert()
        self.info_line_top.fill((250, 250, 250))
        font = pygame.font.Font(None, 36)
        self.text = font.render(text, 1, (10, 10, 10))
        textpos = self.text.get_rect()
        textpos.centerx = self.info_line_top.get_rect().centerx
        self.info_line_top.blit(self.text, textpos)
        self.screen.blit(self.info_line_top, (0, 0))




    def drawGameCanvas(self):
        self.game_canvas = pygame.Surface((500, 500))
        # self.game_canvas = self.game_canvas.convert()
        self.screen.blit(self.game_canvas, (0, 50))

    def drawMunitionLine(self,text):
        # todo: replace numerical display later with munition forms, e.g. small rects
        self.munition_line = pygame.Surface((500, 50))
        # self.munition_line = self.munition_line.convert()
        self.munition_line.fill((250,250,250))
        font = pygame.font.Font(None, 36)
        self.munition_text = font.render(text, 1, (10, 10, 10))
        munition_text_rect = self.munition_text.get_rect()
        munition_text_rect.centerx = self.munition_line.get_rect().centerx
        self.munition_line.blit(self.munition_text, munition_text_rect)
        self.screen.blit(self.munition_line, (0, 450))



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
        self.shooter_delay = 0
        self.ticks_between_two_bullets = 0

        self.enemy_shooting_delay = 0
        self.new_training_values = [[], [], []]
        self.prediction_values = [[], [], []]
        self.c = svm.SVC()
        self.minlen = 100000  # Just a large value to begin with
        self.qp = QtGui.QPainter()
        self.loop_timer.setSingleShot(False)
        self.loop_timer.timeout.connect(self.loop_iteration)
        self.loop_timer.start(35)



    # One iteration of the loop
    def loop_iteration(self):
        #print("A: " + str(self.wm_pointer.accelerometer[1]))
        #print("B: " + str(self.wm_tracker.accelerometer[1]))

        #handles enemies: every few ticks they will shoot based on their location
        # handles delay between shooting of enemies and no shooting
        if self.enemy_shooting_delay <20:
            self.enemy_shooting_delay += 1
        elif (self.enemy_shooting_delay >= 20) & (self.enemy_shooting_delay < 35):
            # handles delay between two enemy bullets
            self.enemy_shooting_delay += 1
            if self.ticks_between_two_bullets < 3:
                self.ticks_between_two_bullets += 1
            else:
                self.ticks_between_two_bullets = 0
                self.enemy.shoot()
        else:
            self.enemy_shooting_delay =0


        # handles drawing mode and disables shooting while drawing
        # allows drawing when the A button on the wiimote is pressed
        if self.wm_pointer.buttons['A']:
            self.game_mode = "draw"
            # todo: draw a shield on the screen --> limit size and duration of appearance
        else:
            self.game_mode = "shoot"
            # disables drawing when shooted
            # allows shooting when the B button on the wiimote is pressed
            if self.wm_pointer.buttons['B']:
                # if munition available, allow shooting
                if self.munition_counter > 0:
                    # adds a delay to firing a bullet so that it will not be fired with each tick, but
                    # with every fifth tick, so that is results not in a long bullet line, but has spaces
                    # between each bullet
                    if(self.shooter_delay < 3):
                        self.shooter_delay += 1
                    else:
                        self.munition_counter -= 1
                        self.player.shoot()
                        self.shooter_delay = 0
                else:
                    print("shooting not possible, reloading necessary")
            # todo: track enemy position
            # todo: track pointer position

        # todo: add check for shields
        # todo: check for collision and handle lives etc.

        # updates the enemies and moves them
        self.all_sprites.update()
        self.screen.fill((100, 100, 100))
        self.all_sprites.draw(self.screen)
        self.recognize_activity(self.wm_pointer.accelerometer)

        pygame.display.flip()

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

        # updates info line on top and munition line on bottom of the game canvas
        self.drawInfoLine("Gesture: " + self.predicted_activity)
        self.drawMunitionLine(str(self.munition_counter) + "/20")
        pygame.display.update(self.munition_line.get_rect())
        pygame.display.update(self.info_line_top.get_rect())

        if self.predicted_activity == "reload":
            if self.munition_counter != 20:
                self.munition_counter = 20


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
    all_sprites = pygame.sprite.Group()

    wiimote_game = WiimoteGame(all_sprites)

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
