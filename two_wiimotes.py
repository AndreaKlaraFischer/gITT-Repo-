#!/usr/bin/env python3

import glob
import sys
import pygame
import wiimote
import math
from PyQt5 import QtWidgets, QtCore, QtGui
import numpy as np
from scipy import fft
from sklearn import svm
from os import path

img_dir = path.join(path.dirname(__file__), 'img')

# This class handles sprite sheets
# This was taken from www.scriptefun.com/transcript-2-using
# sprite-sheets-and-drawing-the-background
# I've added some code to fail if the file wasn't found..
# Note: When calling images_at the rect is the format:
# (x, y, x + offset, y + offset)








#assets:
# crosshairs: https://opengameart.org/content/20-crosshairs-for-re
# explosion: http://1.bp.blogspot.com/-h4gHvGnPfH0/UmFUg1riZlI/AAAAAAAAAFU/FGgUImTIGbU/s640/explosjon3.png
# from http://kidscancode.org/blog/2016/08/pygame_1-2_working-with-sprites/
class Enemy(pygame.sprite.Sprite):
    def __init__(self,  id,x,y,speed):
        # todo: create global constants for width and height and all the other hardcoded numbers
        pygame.sprite.Sprite.__init__(self)
        self.id = id
        self.speed = speed
        self.crosshair_img = pygame.image.load(path.join(img_dir, "dummy_circle.png")).convert()


        self.image = self.crosshair_img
        self.image = pygame.transform.scale(self.crosshair_img, (50, 50))
        self.image.set_colorkey((0, 0, 0))

        self.collisionY = False
        self.collisionX = False
        self.radius = 25
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.enemy_delay = 50
        self.lose_live = False
        self.iterator =0

        self.explosion_sprite = []

        for x in range(1, 17):
            explode_img_1 = pygame.image.load(path.join(img_dir, "explosion_" + str(x) + ".png")).convert()
            self.explosion_sprite.append(explode_img_1)


    def explode(self, iterator):
        # hinder enemy to move any further if he was shooted
        self.speed = 0

        #if self.iterator < len(self.explosion_sprite):
        self.image = pygame.transform.scale(self.explosion_sprite[iterator], (90, 90))
        self.image.set_colorkey((0, 0, 0))
        self.iterator += 1
        # else:
        # self.iterator = 0


    def get_explosion_duration(self):
        return len(self.explosion_sprite)
    # from https://stackoverflow.com/questions/20044791/how-to-make-an-enemy-follow-the-player-in-pygame
    def move_towards_player(self, Player):
        speed = self.speed
        px = Player.rect.centerx
        py = Player.rect.centery
        # Movement along x direction
        if self.rect.centerx > px:
            self.rect.centerx -= speed
            self.collisionX = False
            self.enemy_delay = 50
        elif self.rect.centerx < px:
            self.rect.centerx += speed
            self.collisionX = False
            self.enemy_delay = 50
        else:
            self.collisionX = True
        # Movement along y direction
        if self.rect.centery < py:
            self.rect.centery += speed
            self.collisionY = False
            self.enemy_delay = 50

        elif self.rect.centery > py:
            self.rect.centery -= speed
            self.collisionY = False
            self.enemy_delay = 50
        else:
            self.collisionY = True
        if self.collisionY == True & self.collisionX == True:
            if self.enemy_delay <= 0:
                self.lose_live = True
                print(len(self.explosion_sprite))

            else:
                self.enemy_delay -= 1


    def get_collision(self):
         return self.lose_live


    def reset(self):
        self.rect.x = 10
        self.rect.y = 10
        self.lose_live = False
        self.enemy_delay = 30

# from http://kidscancode.org/blog/2016/08/pygame_shmup_part_1/
class Player(pygame.sprite.Sprite):
    def __init__(self, all_sprites):
        pygame.sprite.Sprite.__init__(self)

        self.WIDTH = pygame.display.get_surface().get_width()
        self.HEIGHT = pygame.display.get_surface().get_height()
        self.all_sprites = all_sprites
        self.image = pygame.Surface((30, 30))
        self.image.fill((0,250,0))
        self.rect = self.image.get_rect()
        self.rect.centerx = self.WIDTH / 2
        self.rect.bottom = self.HEIGHT - 200
        self.speedx = 0



    def update(self):
        self.speedx = 0
        self.speedy =0
        # at the moment the movement of the player is handled via left and right arrows
        keystate = pygame.key.get_pressed()
        if keystate[pygame.K_LEFT]:
            self.speedx = -8
        if keystate[pygame.K_RIGHT]:
            self.speedx = 8
        if keystate[pygame.K_UP]:
            self.speedy = -8
        if keystate[pygame.K_DOWN]:
            self.speedy = 8
        self.rect.x += self.speedx
        self.rect.y += self.speedy
        # prevents the player to get outside of the screen
        if self.rect.right > self.WIDTH:
            # todo: set to pause mode
            self.rect.right = self.WIDTH
        if self.rect.left < 0:
            # todo: set to pause mode
            self.rect.left = 0


    def reset(self):
        self.rect.centerx = self.WIDTH / 2
        self.rect.bottom = self.HEIGHT - 200




class Crosshairs(pygame.sprite.Sprite):
    def __init__(self, all_sprites):
        pygame.sprite.Sprite.__init__(self)
        self.crosshair_img = pygame.image.load(path.join(img_dir, "circle-5.png")).convert()





        self.WIDTH = pygame.display.get_surface().get_width()
        self.HEIGHT = pygame.display.get_surface().get_height()
        self.all_sprites = all_sprites
        self.image = self.crosshair_img
        self.image = pygame.transform.scale(self.crosshair_img, (30, 30))
        self.image.set_colorkey((0,0,0))
        self.radius = 10
        self.rect = self.image.get_rect()


    def update(self):
        mousex, mousey = pygame.mouse.get_pos()
        self.rect.centerx = mousex
        self.rect.centery = mousey




class WiimoteGame(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self.loop_timer = QtCore.QTimer()
        self.init_pygame()
        self.input_device = None
        self.connect_wiimotes()


    # Prepare the audio files
    def init_pygame(self):
        pygame.init()



        self.all_sprites = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.players = pygame.sprite.Group()
        # specific screensize for development, i.e. for displaying the console etc.
        #self.screen = pygame.display.set_mode((500, 500))
        # production mode with fullscreen
        self.screen = pygame.display.set_mode((0,0), pygame.FULLSCREEN)
        self.WIDTH = pygame.display.get_surface().get_width()
        self.HEIGHT = pygame.display.get_surface().get_height()
        pygame.display.set_caption('ITT Final Project')

        self.drawInfoLine("Waiting for gesture ... ")
        self.drawGameCanvas()
        self.drawMunitionLine("20/20")

        # adds an enemy to the canvas. A sprite group is able to hold multiple sprites, i.e. enemies
        enemy = Enemy(1, 10,10,1)
        self.enemies.add(enemy)
        #self.all_sprites.add(enemy)

        enemy = Enemy( 1, self.WIDTH - 50, 10,1)
        self.enemies.add(enemy)
        #self.all_sprites.add(enemy)

        self.crosshairs = Crosshairs(self.all_sprites)

        self.all_sprites.add(self.crosshairs)


        self.player = Player(self.all_sprites)
        self.players.add(self.player)

        self.all_sprites.add(self.player)

        self.enemies.draw(self.screen)
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
        self.info_line_top = pygame.Surface((self.WIDTH, 50))
        self.info_line_top = self.info_line_top.convert()
        self.info_line_top.fill((250, 250, 250))
        font = pygame.font.Font(None, 36)
        self.text = font.render(text, 1, (10, 10, 10))
        textpos = self.text.get_rect()
        textpos.centerx = self.info_line_top.get_rect().centerx
        self.info_line_top.blit(self.text, textpos)
        self.screen.blit(self.info_line_top, (0, 0))




    def drawGameCanvas(self):
        self.game_canvas = pygame.Surface((self.WIDTH, self.HEIGHT))
        # self.game_canvas = self.game_canvas.convert()
        self.screen.blit(self.game_canvas, (0, 50))

    def drawMunitionLine(self,text):
        # todo: replace numerical display later with munition forms, e.g. small rects
        self.munition_line = pygame.Surface((self.WIDTH, 50))
        # self.munition_line = self.munition_line.convert()
        self.munition_line.fill((250,250,250))
        font = pygame.font.Font(None, 36)
        self.munition_text = font.render(text, 1, (10, 10, 10))
        munition_text_rect = self.munition_text.get_rect()
        munition_text_rect.centerx = self.munition_line.get_rect().centerx
        self.munition_line.blit(self.munition_text, munition_text_rect)
        self.screen.blit(self.munition_line, (0, self.HEIGHT-50))



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
            self.input_device = "wiimote"

            # As soon as the Wiimote is connected, start the loop
            self.start_loop()
        else:
            self.input_device = "mouse"
            self.start_loop()

    # Play a sound saved in the vocals dictionary
    def play_sound(self, vocal_name):
        sound = self.vocals[vocal_name]
        sound.play()



    # Starting the game loop
    def start_loop(self):
        self.game_mode = "shoot"
        self.prediction_values = [[], [], []]
        self.last_prediction = "Waiting for data..."
        self.predicted_activity = "-"
        self.category_list = []
        self.munition_counter = 20
        self.lives = 5
        self.shot_enemy = False
        self.highscore = 0
        self.level = 1
        self.level_seconds_counter = 0
        self.hit_enemy = None
        self.new_training_values = [[], [], []]
        self.shooted_enemy = None
        self.prediction_values = [[], [], []]
        self.c = svm.SVC()
        self.shoot_enemy_anim_iterator = 0
        self.minlen = 100000  # Just a large value to begin with
        self.qp = QtGui.QPainter()
        self.loop_timer.setSingleShot(False)
        self.loop_timer.timeout.connect(self.loop_iteration)
        self.loop_timer.start(60)


    def switch_draw_shoot_mode(self):
        if self.input_device == "wiimote":
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
                    x = self.wm_pointer.accelerometer[0]
                    y = self.wm_pointer.accelerometer[1]
                    self.player_shoot(x,y)
                else:
                    print("shooting not possible, reloading necessary")

    def player_shoot(self,x,y):
        for enemy in self.enemies:
            dist = math.hypot(x - enemy.rect.centerx, y - enemy.rect.centery)
            # smaller than enemy radius
            if dist < 25:
                if self.check_munition_available() == True:
                    #self.enemies.remove(enemy)
                    self.munition_counter -= 1
                    self.highscore += 100
                    self.shot_enemy = True
                    self.shooted_enemy = enemy

                else:
                    print("no munition. press RETURN on keyboard or shake wiimote")
                # todo: or instead of removing make enemy smaller before it completely disappears?



    def check_enemy_behind(self):
        for enemy in self.enemies:
            check_for_overlapping = enemy.get_collision()
            if (check_for_overlapping == True):
                enemy.reset()
                self.player.reset()
                if (self.lives > 0):
                    self.lives -= 1


                else:
                    print("show highscore screen")
                    # todo: implement highscore screen stuff and csv saving

    def check_level(self):
        if self.level_seconds_counter > 600:
            self.level_seconds_counter = 0
            self.level += 1
            enemy = Enemy(1, self.WIDTH/2, 0, 1)
            self.enemies.add(enemy)
            #self.all_sprites.add(enemy)
        else:
            self.level_seconds_counter +=1

    # One iteration of the loop
    def loop_iteration(self):
        self.highscore += 1

        self.check_level()

        self.switch_draw_shoot_mode()
        # todo: add check for shields
        self.enemies.update()
        # updates the enemies and moves them
        self.all_sprites.update()
        # enemy should follow the player
        for enemy in self.enemies:
            enemy.move_towards_player(self.player)

        # check for overlapping with enemy
        self.check_enemy_behind()

        self.draw_explosion()

        # update the screen and draw all sprites on new positions
        self.screen.fill((100, 100, 100))
        self.enemies.draw(self.screen)
        self.all_sprites.draw(self.screen)
        # recognize gesture
        if self.input_device == "wiimote":
            self.recognize_activity(self.wm_pointer.accelerometer)

        # updates info line on top and munition line on bottom of the game canvas
        self.drawInfoLine("Lives: " + str(self.lives) + "/5 Gesture: " + self.predicted_activity + " Highscore: " + str(
                    self.highscore))
        self.drawMunitionLine(str(self.munition_counter) + "/20")
        pygame.display.update(self.munition_line.get_rect())
        pygame.display.update(self.info_line_top.get_rect())

        pygame.display.flip()
        self.init_pygame_events()


    def draw_explosion(self):
        if self.shot_enemy == True:
            if self.shoot_enemy_anim_iterator < self.shooted_enemy.get_explosion_duration():
                self.shooted_enemy.explode(self.shoot_enemy_anim_iterator)
                self.shoot_enemy_anim_iterator += 1
            else:
                self.enemies.remove(self.shooted_enemy)
                self.shot_enemy = False
                self.shoot_enemy_anim_iterator = 0
                self.shooted_enemy = None

    def init_pygame_events(self):
        # necessary for closing the window in pygame
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    exit()
                elif event.key == pygame.K_RETURN:
                    self.munition_counter = 20
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # check for collision with crosshairs and enemy
                x = pygame.mouse.get_pos()[0]
                y = pygame.mouse.get_pos()[1]
                self.player_shoot(x,y)



    def check_munition_available(self):
        if(self.munition_counter > 0):
            return True
        else:
            return False

    def recognize_activity(self, accelerometer):
        x_acc = accelerometer[0]
        y_acc = accelerometer[1]
        z_acc = accelerometer[2]
        #print(x_acc,y_acc,z_acc)

        # todo: if available, recognizing should be started, and if not add training data with gesture name
        # checks for available training data.
        self.read_data_from_csv()
        self.predicted_activity = self.predict_activity(x_acc,y_acc,z_acc)



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


    wiimote_game = WiimoteGame()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
