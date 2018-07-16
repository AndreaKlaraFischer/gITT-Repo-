#!/usr/bin/env python3

import glob
import sys
import pygame
import wiimote
import math
import time
from random import randint
from PyQt5 import QtWidgets, QtCore, QtGui
import numpy as np
from scipy import fft
from sklearn import svm
from os import path

# defines the directory where all images are located
img_dir = path.join(path.dirname(__file__), 'img')


#assets:
# crosshairs: https://opengameart.org/content/20-crosshairs-for-re
# explosion: http://1.bp.blogspot.com/-h4gHvGnPfH0/UmFUg1riZlI/AAAAAAAAAFU/FGgUImTIGbU/s640/explosjon3.png
# circle (temporary): https://www.kisspng.com/png-circle-rainbow-free-content-clip-art-rainbow-borde-175522/download-png.html
# from http://kidscancode.org/blog/2016/08/pygame_1-2_working-with-sprites/
# Sound "shot.wav": https://freesound.org/people/LeMudCrab/sounds/163455/ (CC0 1.0)
# Sound "reload.wav": https://freesound.org/people/niamhd00145229/sounds/422688/ (CC0 1.0)

class Constants:
    WIIMOTE_IR_CAM_WIDTH = 1024
    ENEMY_DELAY = 30
    DURATION_BETWEEN_ENEMIES = 100
    WIIMOTE_IR_CAM_HEIGHT = 768
    CROSSHAIR_SIZE  = 100
    WIIMOTE_IR_CAM_CENTER = (WIIMOTE_IR_CAM_WIDTH/2, WIIMOTE_IR_CAM_HEIGHT/2)

    #WIDTH = pygame.display.get_surface().get_width()
    #HEIGHT = pygame.display.get_surface().get_height()


class Enemy(pygame.sprite.Sprite):
    def __init__(self,  id,x,y,speed):
        # todo: create global constants for width and height and all the other hardcoded numbers
        pygame.sprite.Sprite.__init__(self)
        self.id = id
        self.speed = speed

        # sets the image of the enemy objects
        self.circle_img = pygame.image.load(path.join(img_dir, "dummy_circle.png")).convert()
        self.image = self.circle_img
        # scales down image
        self.image = pygame.transform.scale(self.circle_img, (50, 50))
        # avoids a black background
        self.image.set_colorkey((0, 0, 0))

        # specifies position of enemy
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y

        # init
        self.enemy_delay = Constants.ENEMY_DELAY
        self.lose_live = False
        self.explosion_sprite = []
        self.collisionY = False
        self.collisionX = False

        # creates a list of all explosion images
        for x in range(1, 17):
            explode_img_1 = pygame.image.load(path.join(img_dir, "explosion_" + str(x) + ".png")).convert()
            self.explosion_sprite.append(explode_img_1)


    def explode(self, iterator):
        # hinder enemy to move any further if he was shooted
        self.speed = 0
        # sets explosion image to image in list index defined by iterator that is passed in update method
        self.image = pygame.transform.scale(self.explosion_sprite[iterator], (90, 90))
        self.image.set_colorkey((0, 0, 0))


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
            self.enemy_delay = Constants.ENEMY_DELAY
        elif self.rect.centerx < px:
            self.rect.centerx += speed
            self.collisionX = False
            self.enemy_delay = Constants.ENEMY_DELAY
        else:
            self.collisionX = True
        # Movement along y direction
        if self.rect.centery < py:
            self.rect.centery += speed
            self.collisionY = False
            self.enemy_delay = Constants.ENEMY_DELAY
        elif self.rect.centery > py:
            self.rect.centery -= speed
            self.collisionY = False
            self.enemy_delay = Constants.ENEMY_DELAY
        else:
            self.collisionY = True
        if self.collisionY == True & self.collisionX == True:
            # adds a delay after that the player will lose a live
            if self.enemy_delay <= 0:
                self.lose_live = True
            else:
                self.enemy_delay -= 1

    # returns whether an enemy is overlapped with the player
    def get_collision(self):
         return self.lose_live

    # resets enemy to start position
    def reset(self):
        self.rect.x = 10
        self.rect.y = 10
        self.lose_live = False
        self.enemy_delay = Constants.ENEMY_DELAY

# from http://kidscancode.org/blog/2016/08/pygame_shmup_part_1/
class Player(pygame.sprite.Sprite):
    def __init__(self):
        pygame.sprite.Sprite.__init__(self)
        self.WIDTH = pygame.display.get_surface().get_width()
        self.HEIGHT = pygame.display.get_surface().get_height()
        self.image = pygame.Surface((100, 100))
        self.image.fill((0, 255, 0))
        self.rect = self.image.get_rect()
        self.rect.centerx = self.WIDTH / 2
        self.rect.bottom = self.HEIGHT - 200
        self.speedx = 0
        self.centerx = self.WIDTH /2
        self.centery = self.HEIGHT/2

    def set_player_coordinates(self, x, y):
        self.centerx = x
        self.centery = y

    # moves player based on keyboard input
    # todo: change player movement by headtracking coordinates
    def update(self):
        self.speedx = 0
        self.speedy = 0
        # at the moment the movement of the player is handled via left and right arrows
        """
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
        """
        self.rect.x = self.centerx
        self.rect.y = self.centery

        # prevents the player to get outside of the screen
        if self.rect.right > self.WIDTH:
            # todo: set to pause mode
            self.rect.right = self.WIDTH
        if self.rect.left < 0:
            # todo: set to pause mode
            self.rect.left = 0

    # resets player to start position
    def reset(self):
        self.rect.centerx = self.WIDTH / 2
        self.rect.bottom = self.HEIGHT - 200


class Crosshairs(pygame.sprite.Sprite):
    def __init__(self):
        pygame.sprite.Sprite.__init__(self)
        # set crosshair image
        self.crosshair_img = pygame.image.load(path.join(img_dir, "circle-5.png")).convert()
        self.WIDTH = pygame.display.get_surface().get_width()
        self.HEIGHT = pygame.display.get_surface().get_height()
        self.image = self.crosshair_img
        self.image = pygame.transform.scale(self.crosshair_img, (Constants.CROSSHAIR_SIZE, Constants.CROSSHAIR_SIZE))
        self.image.set_colorkey((0,0,0))
        self.radius = 10
        self.rect = self.image.get_rect()

        pygame.mouse.set_cursor((8,8),(0,0),(0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0))

    # display crosshairs on mouse position
    def update(self):
        mousex, mousey = pygame.mouse.get_pos()
        self.rect.centerx = mousex
        self.rect.centery = mousey


class WiimoteGame(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()

        self.WIIMOTE_IR_CAM_WIDTH = 1024
        self.WIIMOTE_IR_CAM_HEIGHT = 768
        self.WIIMOTE_IR_CAM_CENTER = (self.WIIMOTE_IR_CAM_WIDTH/2, self.WIIMOTE_IR_CAM_HEIGHT/2)

        self.pointer_x_values = []
        self.pointer_y_values = []

        self.sounds = {}

        self.last_button_press = time.time()

        self.init_pygame()
        self.input_device = "wiimote"
        self.connect_wiimotes()

    def init_pygame(self):
        pygame.init()
        self.init_canvas()
        self.init_sprites()
        # updates complete pygame display
        pygame.display.flip()
        self.clock = pygame.time.Clock()
        self.init_sounds()

    def init_canvas(self):
       # specific screensize for development, i.e. for displaying the console etc.:
       #self.screen = pygame.display.set_mode((500, 500))
       # production mode with fullscreen:
       self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
       self.WIDTH = pygame.display.get_surface().get_width()
       self.HEIGHT = pygame.display.get_surface().get_height()
       pygame.display.set_caption('ITT Final Project')
       self.drawInfoLine("Waiting for gesture ... ")
       self.drawGameCanvas()
       self.drawMunitionLine("20/20")

    def drawInfoLine(self, text):
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
        self.screen.blit(self.game_canvas, (0, 50))

    def drawMunitionLine(self, text):
        # todo: replace numerical display later with munition forms, e.g. small rects
        self.munition_line = pygame.Surface((self.WIDTH, 50))
        self.munition_line.fill((250, 250, 250))
        font = pygame.font.Font(None, 36)
        self.munition_text = font.render(text, 1, (10, 10, 10))
        munition_text_rect = self.munition_text.get_rect()
        munition_text_rect.centerx = self.munition_line.get_rect().centerx
        self.munition_line.blit(self.munition_text, munition_text_rect)
        self.screen.blit(self.munition_line, (0, self.HEIGHT - 50))

    def init_sprites(self):
        # adds all sprites, i.e. game elements to the screen
        self.all_sprites = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.players = pygame.sprite.Group()
        enemy = Enemy(1, 0, 0, 1)
        self.enemies.add(enemy)
        enemy = Enemy(2, self.WIDTH, 0, 1)
        self.enemies.add(enemy)

        enemy = Enemy(3, 0, self.HEIGHT, 1)
        self.enemies.add(enemy)

        enemy = Enemy(4, self.WIDTH, self.HEIGHT, 1)
        self.enemies.add(enemy)

        self.crosshairs = Crosshairs()
        self.all_sprites.add(self.crosshairs)
        self.player = Player()
        self.players.add(self.player)
        self.all_sprites.add(self.player)
        # draws all game elements
        self.enemies.draw(self.screen)
        self.all_sprites.draw(self.screen)

    def init_sounds(self):
        try:
            # Init Sounds here (the soundfiles need to be in folder "assets"
            self.sounds = {
                "shot": pygame.mixer.Sound(path.join("assets", "shot.wav")),
                "reload": pygame.mixer.Sound(path.join("assets", "reload.wav"))
            }
            print(path.join("sounds", "stronger.wav"))
            print(self.sounds)
        except pygame.error:
            print("Missing audio files!")
            print(pygame.error)
            sys.exit()

    # Play a sound saved in the sounds dictionary
    def play_sound(self, sound_name):
        sound = self.sounds[sound_name]
        sound.play()

    # Start the pairing process, like in wiimote_demo.py
    def connect_wiimotes(self):

        name_tracker = None
        name_pointer = None

        if len(sys.argv) == 1:
            # mode with hardcoded bluetooth mac adresses; no arguments should be passed
            tracker = "00:1e:a9:36:9b:34"
            pointer = "B8:AE:6E:55:B5:0F"
            self.wm_pointer = wiimote.connect(pointer, name_pointer)
            self.wm_tracker = wiimote.connect(tracker, name_tracker)


            self.wm_pointer.ir.register_callback(self.get_ir_data_of_pointer)
            self.wm_tracker.ir.register_callback(self.get_ir_data_of_tracker)

            self.wm_pointer.leds = [1, 0, 0, 0]
            self.wm_tracker.leds = [0, 1, 0, 0]

            self.wm = self.wm_pointer
            self.input_device = "wiimote"
            # As soon as the Wiimote is connected, start the loop
            self.start_loop()
        if len(sys.argv) == 2:
            # mode with one hardcoded bluetooth mac adress; one argument should be passed
            pointer = "B8:AE:6E:F1:39:81"
            self.wm_pointer = wiimote.connect(pointer, name_pointer)
            #self.wm_pointer.ir.register_callback(self.get_ir_data_of_pointer)

            self.wm_pointer.leds = [1, 0, 0, 0]

            self.wm = self.wm_pointer
            self.input_device = "wiimote"
            # As soon as the Wiimote is connected, start the loop
            self.start_loop()
        # mode with bluetooth mac adresses on stdin, 2 adresses should be passed
        if len(sys.argv) == 3:
            tracker = sys.argv[1]
            pointer = sys.argv[2]
            self.wm_tracker = wiimote.connect(tracker, name_tracker)
            self.wm_pointer = wiimote.connect(pointer, name_pointer)

            self.wm_tracker.ir.register_callback(self.get_ir_data_of_tracker)
            self.wm_pointer.ir.register_callback(self.get_ir_data_of_pointer)
            self.wm_pointer.leds = [1, 0, 0, 0]
            self.wm_tracker.leds = [0, 1, 0, 0]

            self.wm = self.wm_pointer
            self.input_device = "wiimote"
            # As soon as the Wiimote is connected, start the loop
            self.start_loop()
        # mode with mouse for testing purposes
        elif len(sys.argv) == 4:
            self.input_device = "mouse"
            self.start_loop()

    # Get the IR data from the "Pointer" Wiimote
    def get_ir_data_of_pointer(self, ir_data):
        if len(ir_data) == 4:
            led_one = (ir_data[0]["x"], ir_data[0]["y"])
            led_two = (ir_data[1]["x"], ir_data[1]["y"])
            led_three = (ir_data[2]["x"], ir_data[2]["y"])
            led_four = (ir_data[3]["x"], ir_data[3]["y"])

            if led_one[0] == 1023 and led_one[1] == 1023:
                return

            self.pointing = Pointing()

            # print(led_one, led_two, led_three, led_four)
            x, y = self.pointing.process_ir_data(led_one, led_two, led_three, led_four)

            self.pointer_x_values.append(x)
            self.pointer_y_values.append(y)
            if len(self.pointer_x_values) == 10:
                filtered_x, filtered_y = self.moving_average(self.pointer_x_values, self.pointer_y_values)
                print(self.pointer_x_values)
                self.pointer_x_values = []
                self.pointer_y_values = []
                pygame.mouse.set_pos([filtered_x, filtered_y])

    # Simple implementation
    def moving_average(self, x_values, y_values):
        sum_of_x = 0
        sum_of_y = 0
        for i in range(len(x_values)):
            sum_of_x += x_values[i]
            sum_of_y += y_values[i]

        filtered_x = sum_of_x/len(x_values)
        filtered_y = sum_of_y/len(y_values)

        return filtered_x, filtered_y


    # Get the IR data from the "Tacker" Wiimote
    def get_ir_data_of_tracker(self, ir_data):
        if len(ir_data) == 2:
            left = (ir_data[0]["x"], ir_data[0]["y"])
            right = (ir_data[1]["x"], ir_data[1]["y"])

            print(left, right)

            if left[0] == 1023 and left[1] == 1023:
                return

            self.tracking = Tracking()
            x_on_screen, y_on_screen = self.tracking.process_ir_data(left, right)
            # Pass the coordinates to the player.
            self.player.set_player_coordinates(x_on_screen, y_on_screen)

    # Starting the game loop
    def start_loop(self):
        # todo: check later if all of these are still used
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
        self.reload_delay = 50

        self.hit_enemy = None
        self.new_training_values = [[], [], []]
        self.shooted_enemy = None
        self.prediction_values = [[], [], []]
        self.c = svm.SVC()
        self.game_over = False

        self.shoot_enemy_anim_iterator = 0
        self.minlen = 100000  # Just a large value to begin with

        running = True
        while running:
            self.loop_iteration()

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
                    if self.new_click_ok(time.time()):
                        x = pygame.mouse.get_pos()[0]
                        y = pygame.mouse.get_pos()[1]
                        self.player_shoot(x,y)

    # Check if a button press on the wiimote has happened within the last 0.1 seconds
    # This prevents a sound from being played twice if a user presses a button too long.
    def new_click_ok(self, current_time):
        if current_time - self.last_button_press > 0.1:
            self.last_button_press = current_time
            return True
        else:
            self.last_button_press = current_time
            return False



    # if the player shoots an enemy
    def player_shoot(self, x, y):
        if self.check_munition_available() == True:
            self.munition_counter -= 1
            self.play_sound("shot")
            print("Pos Crosshair", x, y)

        else:
            print("no munition. press RETURN on keyboard or shake wiimote")
            return
        # todo: or instead of removing make enemy smaller before it completely disappears?

        # check for each enemy, if the mouse or wiimote, i.e. x and y are within an enemy
        for enemy in self.enemies:
            dist = math.hypot(x - enemy.rect.centerx, y - enemy.rect.centery)
            # needs to be smaller than enemy radius
            if dist < 50:
                self.shot_enemy = True
                self.shooted_enemy = enemy


    # checks if the player is overlapped by an enemy
    def check_enemy_behind(self):
        for enemy in self.enemies:
            # is true as soon as the enemy waiting delay is over
            check_for_overlapping = enemy.get_collision()
            if (check_for_overlapping == True):
                enemy.reset()
                self.player.reset()
                if (self.lives > 0):
                    self.lives -= 1
                else:
                    self.game_over = True
                    print("show highscore screen")
                    # todo: implement highscore screen stuff and csv saving

   # counts minutes and adds a new enemy after each minute
    def check_level(self):
        position_arr_x = [0,self.WIDTH]
        position_arr_y = [0, self.HEIGHT]
        if self.level_seconds_counter > Constants.DURATION_BETWEEN_ENEMIES:
            self.level_seconds_counter = 0
            self.level += 1
            enemy = Enemy(1, position_arr_x[randint(0, 1)], position_arr_y[randint(0,1)], 1)
            self.enemies.add(enemy)
        else:
            self.level_seconds_counter +=1

    # One iteration of the loop
    def loop_iteration(self):
        if self.game_over == False:
            self.clock.tick(60)
            self.check_level()
            self.switch_draw_shoot_mode()
            # todo: add check for shields

            # updates the enemies and moves them
            self.enemies.update()
            self.all_sprites.update()

            # enemy should follow the player
            for enemy in self.enemies:
                enemy.move_towards_player(self.player)

            # check for overlapping with enemy
            self.check_enemy_behind()

            # draws explosion, if the player has shot an enemy
            self.draw_explosion()

            # update the screen and draw all sprites on new positions
            self.screen.fill((100, 100, 100))
            self.enemies.draw(self.screen)
            self.all_sprites.draw(self.screen)

            # recognize gesture
            if self.input_device == "wiimote":
                if (self.get_rotation() == True):
                    self.recognize_activity(self.wm_pointer.accelerometer)

            # updates info line on top and munition line on bottom of the game canvas
            self.drawInfoLine(
                "Lives: " + str(self.lives) + "/5 Gesture: " + self.predicted_activity + " Highscore: " + str(
                    self.highscore))
            self.drawMunitionLine(str(self.munition_counter) + "/20")
            pygame.display.update(self.munition_line.get_rect())
            pygame.display.update(self.info_line_top.get_rect())

            pygame.display.flip()
            self.init_pygame_events()

        else:
            self.clock.tick(60)

            self.screen.fill((100, 100, 100))


            font = pygame.font.Font(None, 36)
            self.text = font.render("You lost!", 1, (10, 10, 10))
            textpos = self.text.get_rect()
            self.screen.blit(self.text, (250, 250))

            pygame.display.flip()
            self.init_pygame_events()



    def get_rotation(self):
        if self.wm.accelerometer[1] < 450:
            return True



    # draws an explosion animation, if the player has just shot an enemy
    def draw_explosion(self):
        if self.munition_counter > 0:
            if self.shot_enemy == True:
                # increase the number of the enemy sprite image with each tick and draw image
                if self.shoot_enemy_anim_iterator < self.shooted_enemy.get_explosion_duration():
                    self.shooted_enemy.explode(self.shoot_enemy_anim_iterator)
                    self.shoot_enemy_anim_iterator += 1
                else:
                    self.highscore += 100
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
                if self.reload_delay >= 50:
                    print("reload")
                    self.reload_delay = 0
                    self.munition_counter = 20
                else:
                    self.reload_delay += 1

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


"""This class gets the coordinates of four LEDs as input params and calculates the coordinates of point the player is pointing at"""
class Pointing:

    # Code taken from the Jupyter Notebook "Projective Transformations" from GRIPS
    def process_ir_data(self, led_one, led_two, led_three, led_four):

        A = led_one
        B = led_two
        C = led_three
        D = led_four

        #The following 16 lines of code responsible for sorting are taken from the file "transform.py" of Andrea Fischers and Miriam Schlindweins solution of of Assignment09
        points = [A, B, C, D]
        points = sorted(points, key=lambda k: k[0])

        if points[0][1] < points[1][1]:
            A = points[0]
            B = points[1]
        else:
            A = points[1]
            B = points[0]

        if points[2][1] < points[3][1]:
            D = points[2]
            C = points[3]
        else:
            D = points[3]
            C = points[2]


        #TEMP:
        DESTINATION_SCREEN_WIDTH = 1920
        DESTINATION_SCREEN_HEIGHT = 1080

         # Step 1
        source_points_123 = np.matrix([[A[0], B[0], C[0]], [A[1], B[1], C[1]], [1, 1, 1]])
        source_point_4 = [[D[0]], [D[1]], [1]]

        scale_to_source = np.linalg.solve(source_points_123, source_point_4)
        l, m, t = [float(x) for x in scale_to_source]

        # Step 2
        unit_to_source = np.matrix([[l * A[0], m * B[0], t * C[0]], [l * A[1], m * B[1], t* C[1]], [l, m, t]])

        # Step 3
        A2 = 0, DESTINATION_SCREEN_HEIGHT
        B2 = 0, 0
        C2 = DESTINATION_SCREEN_WIDTH, 0
        D2 = DESTINATION_SCREEN_WIDTH, DESTINATION_SCREEN_HEIGHT

        dest_points_123 = np.matrix([[A2[0], B2[0], C2[0]], [A2[1], B2[1], C2[1]], [1 , 1, 1]])

        dest_point_4 = np.matrix([[D2[0]], [D2[1]], [1]])

        scale_to_dest = np.linalg.solve(dest_points_123, dest_point_4)
        l,m,t = [float(x) for x in scale_to_dest]

        unit_to_dest = np.matrix([[l * A2[0], m * B2[0], t * C2[0]], [l * A2[1], m * B2[1], t * C2[1]],  [l, m, t]])

        # Step 4: Invert  A  to obtain  A−1
        source_to_unit = np.linalg.inv(unit_to_source)

        # Step 5: Compute the combined matrix
        source_to_dest = unit_to_dest @ source_to_unit

        # Step 6: To map a location  (x,y)  from the source image to its corresponding location in the destination image, compute the product
        x,y,z = [float(w) for w in (source_to_dest @ np.matrix([[512], [384], [1]]))]

        # step 7: dehomogenization
        x = int(x / z)
        y = int(y / z)

        return x, y


"""This class gets the coordinates of the two LEDs of the head tracking device as input and calculates the position of the player on the screen"""
class Tracking:

    def process_ir_data(self, left, right):

        #Temp:
        self.WIDTH = 1920
        self.HEIGHT = 1080

        # Since we want direct movement (e.g move head up -> move player on screen up), the coordinate points need to be inverted. Otherwise, movements will be in the wrong direction
        inverted_left = (Constants.WIIMOTE_IR_CAM_WIDTH - left[0], Constants.WIIMOTE_IR_CAM_HEIGHT - left[1])
        inverted_right = (Constants.WIIMOTE_IR_CAM_WIDTH - right[0], Constants.WIIMOTE_IR_CAM_HEIGHT - right[1])

        # After getting the coordinates of the two LEDs, we need to calculate the point in the middle of the two coordinates. This is the center of our head.
        center = ((inverted_left[0] + inverted_right[0]) / 2, (inverted_left[1] + inverted_right[1]) / 2)

        # The coordinates of the head center are for the resolution of the Wiimote IR Cam (1024x768). To position the player correctly on the screen, new coordinates need to be calculated, suited for the resolution of the screen.
        x_on_screen = int((center[0] / Constants.WIIMOTE_IR_CAM_WIDTH) * self.WIDTH)
        y_on_screen = int((center[1] / Constants.WIIMOTE_IR_CAM_HEIGHT) * self.HEIGHT)

        print("X on screen: ", x_on_screen)
        print("Y on screen: ", y_on_screen)
        return x_on_screen, y_on_screen


def main():
    app = QtWidgets.QApplication(sys.argv)


    wiimote_game = WiimoteGame()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
