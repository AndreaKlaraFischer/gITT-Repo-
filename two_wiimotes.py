#!/usr/bin/env python3

import glob
import sys
import pygame
import wiimote
import math
import time
import csv
import numpy as np
from random import randint
from scipy import fft
from sklearn import svm
from os import path

"""
Sources:
    Sprites:
    # crosshairs: https://opengameart.org/content/20-crosshairs-for-re
    # explosion: http://1.bp.blogspot.com/-h4gHvGnPfH0/UmFUg1riZlI/AAAAAAAAAFU/FGgUImTIGbU/s640/explosjon3.png
    # Enemies: http://edmundmcmillen.tumblr.com/post/25278589277/click-the-image-to-view-it-at-full-rez-so-the
    # Heart: https://opengameart.org/content/heart-2 (CC0 1.0)
    # Bullet: https://opengameart.org/content/weapon-icons-1 by BrighamKeys(CC-BY-SA 3.0)

    Sounds:
    # Sound "shot.wav": https://freesound.org/people/LeMudCrab/sounds/163455/ (CC0 1.0)
    # Sound "reload.wav": https://freesound.org/people/IchBinJager/sounds/272068/ by IchBinJager (CC BY 3.0)
    # Sound "ouch.wav": 
"""

"""For easy access to constants from all classes, they had been put into their own class"""
class Constants:
    WIIMOTE_IR_CAM_WIDTH = 1024
    ENEMY_DELAY = 30
    DURATION_BETWEEN_ENEMIES = 150
    WIIMOTE_IR_CAM_HEIGHT = 768
    CROSSHAIR_SIZE  = 100
    WIIMOTE_IR_CAM_CENTER = (WIIMOTE_IR_CAM_WIDTH/2, WIIMOTE_IR_CAM_HEIGHT/2)
    MOVING_AVERAGE_NUM_VALUES = 5  # num of values that should be buffered for moving average filter

    WIIMOTE_TRACKER_ADDRESS = "B8:AE:6E:55:B5:0F"
    WIIMOTE_POINTER_ADDRESS = "B8:AE:6E:55:B5:0F"

    ENEMY_SIZE = 100
    BULLET_HOLE_SIZE = 10
    BARRICADE_LIVETIME = 5  # Seconds
    MUNITION_COUNT = 10
    MAX_NUM_LIVES = 5

    # defines the directory where all images are located
    IMG_DIR = path.join(path.dirname(__file__), 'img')
    GAME_BACKGROUND = None


class WiimoteGame:

    def __init__(self):
        super().__init__()

        self.gesture_recognizer = GestureRecognizer()
        self.activity_recognizer = ActivityRecognizer()

        self.pointer_x_values = []
        self.pointer_y_values = []

        self.drawing_x_values = []
        self.drawing_y_values = []
        self.currently_drawing = False
        self.barricade = {}

        self.bullet_holes = []

        self.sounds = {}
        self.input_device = "wiimote"
        self.last_button_press = time.time()

        self.init_pygame()
        self.connect_wiimotes()

    def init_pygame(self):
        pygame.init()
        self.init_canvas()
        self.init_sprites()

        pygame.display.flip() # updates complete pygame display
        self.clock = pygame.time.Clock()
        self.init_sounds()

    def init_canvas(self):
       #self.screen = pygame.display.set_mode((500, 500))
       self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)

       self.WIDTH = pygame.display.get_surface().get_width()
       self.HEIGHT = pygame.display.get_surface().get_height()

       self.drawInfoLine("Highscore: 0")
       self.drawGameCanvas()
       self.drawMunitionLine(Constants.MUNITION_COUNT, Constants.MAX_NUM_LIVES)

    def drawInfoLine(self, text):
        self.info_line_top = pygame.Surface((self.WIDTH, 50))
        self.info_line_top = self.info_line_top.convert()
        self.info_line_top.fill((250, 250, 250))
        font = pygame.font.Font(None, 50)
        self.text = font.render(text, 1, (10, 10, 10))
        textpos = self.text.get_rect()
        textpos.centerx = self.info_line_top.get_rect().centerx
        self.info_line_top.blit(self.text, textpos)
        self.screen.blit(self.info_line_top, (0, 0))

    def drawGameCanvas(self):
        self.game_canvas = pygame.Surface((self.WIDTH, self.HEIGHT))
        self.screen.blit(self.game_canvas, (0, 50))

    def drawMunitionLine(self, num_bullets, lives):
        self.munition_line = pygame.Surface((self.WIDTH, 50))
        self.munition_line.fill((250, 250, 250))
        self.screen.blit(self.munition_line, (0, self.HEIGHT - 50))

        bullet = pygame.image.load(path.join(Constants.IMG_DIR, "bullet.png"))
        for i in range(num_bullets):
            self.screen.blit(bullet, (self.WIDTH - i*20,self.HEIGHT - 50, 100, 100))

        heart = pygame.image.load(path.join(Constants.IMG_DIR, "heart.png"))
        for i in range(lives):
            self.screen.blit(heart, (i*50 + 10, self.HEIGHT - 40, 100, 100))

    # adds all sprites, i.e. game elements to the screen
    def init_sprites(self):
        self.all_sprites = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.players = pygame.sprite.Group()
        enemy = Enemy(1, 0, 0, 1,randint(1,5))
        self.enemies.add(enemy)
        #enemy = Enemy(2, self.WIDTH, 0, 1)
        #self.enemies.add(enemy)

        #enemy = Enemy(3, 0, self.HEIGHT, 1)
        #self.enemies.add(enemy)

        #enemy = Enemy(4, self.WIDTH, self.HEIGHT, 1)
        #self.enemies.add(enemy)

        self.crosshairs = Crosshairs()
        self.all_sprites.add(self.crosshairs)
        self.player = Player()
        self.players.add(self.player)
        self.all_sprites.add(self.player)
        self.enemies.draw(self.screen)
        self.all_sprites.draw(self.screen)

    def init_sounds(self):
        try:
            self.sounds = {
                "shot": pygame.mixer.Sound(path.join("sounds", "shot.wav")),
                "reload": pygame.mixer.Sound(path.join("sounds", "reload.wav")),
                "ouch": pygame.mixer.Sound(path.join("sounds", "ouch.wav")),
                "no_ammo": pygame.mixer.Sound(path.join("sounds", "no_ammo.wav"))
            }
        except pygame.error:
            print("Missing audio files!")
            sys.exit()

    # Play a sound saved in the sounds dictionary
    def play_sound(self, sound_name):
        sound = self.sounds[sound_name]
        sound.play()

    # Start the pairing process, like in wiimote_demo.py
    def connect_wiimotes(self):

        tracker = Constants.WIIMOTE_TRACKER_ADDRESS
        pointer = Constants.WIIMOTE_POINTER_ADDRESS

        if len(sys.argv) == 4: # Developement mode for mouse
            self.input_device = "mouse"
            self.start_loop()
            return

        if len(sys.argv) == 2: # Developement mode for testing only the pointing; one argument should be passed
            pointer = Constants.WIIMOTE_POINTER_ADDRESS

        if len(sys.argv) == 1:
            # mode with hardcoded bluetooth mac adresses in Constants class; no arguments should be passed
            #self.wm_tracker = wiimote.connect(tracker, None)
            #self.wm_tracker.ir.register_callback(self.get_ir_data_of_tracker)
            #self.wm_tracker.leds = [0, 1, 0, 0]
            pass

        # mode with bluetooth mac adresses on stdin, 2 adresses should be passed
        if len(sys.argv) == 3:
            tracker = sys.argv[1]
            pointer = sys.argv[2]
            self.wm_tracker = wiimote.connect(tracker, None)
            self.wm_tracker.ir.register_callback(self.get_ir_data_of_tracker)
            self.wm_tracker.leds = [0, 1, 0, 0]

        self.wm_pointer = wiimote.connect(pointer, None)
        self.wm_pointer.ir.register_callback(self.get_ir_data_of_pointer)
        self.wm_pointer.leds = [1, 0, 0, 0]

        self.tracking = Tracking()
        self.pointing = Pointing()

        # As soon as the Wiimotes are connected, start the loop
        self.start_loop()

    # Get the IR data from the "Pointer" Wiimote
    def get_ir_data_of_pointer(self, ir_data):
        if len(ir_data) == 4:
            led_one = (ir_data[0]["x"], ir_data[0]["y"])
            led_two = (ir_data[1]["x"], ir_data[1]["y"])
            led_three = (ir_data[2]["x"], ir_data[2]["y"])
            led_four = (ir_data[3]["x"], ir_data[3]["y"])

            # Check if the Wiimote is outputting wrong values (If IR is not working, x and y values will be 1023)
            if led_one[0] == 1023 and led_one[1] == 1023:
                return

            # print(led_one, led_two, led_three, led_four)
            x, y = self.pointing.process_ir_data(led_one, led_two, led_three, led_four)

            self.pointer_x_values.append(x) #  Collect values in list
            self.pointer_y_values.append(y)

            # Filter values using the moving average filter
            if len(self.pointer_x_values) == Constants.MOVING_AVERAGE_NUM_VALUES:
                filtered_x, filtered_y = self.moving_average(self.pointer_x_values, self.pointer_y_values)
                self.pointer_x_values = []
                self.pointer_y_values = []
                pygame.mouse.set_pos([filtered_x, filtered_y]) # Move the mouse

    # Simple implementation of the moving average filter
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

            # Check if the Wiimote is outputting wrong values. (If IR is not working, x and y values will be 1023)
            if left[0] == 1023 and left[1] == 1023:
                return

            x_on_screen, y_on_screen = self.tracking.process_ir_data(left, right)
            # Pass the coordinates to the player.
            self.player.set_player_coordinates(x_on_screen, y_on_screen)

    # Starting the game loop
    def start_loop(self):
        # todo: check later if all of these are still used
        self.munition_counter = Constants.MUNITION_COUNT
        self.lives = Constants.MAX_NUM_LIVES
        self.highscore = 0
        self.shot_enemy = False
        self.restarted = False
        self.level_seconds_counter = 0
        self.hit_enemy = None
        self.shooted_enemy = None
        self.game_over = False
        self.shoot_enemy_anim_iterator = 0

        running = True
        while running:
            self.loop_iteration()

    # One iteration of the loop
    def loop_iteration(self):
        if self.game_over == False:
            self.restarted = False
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

            self.check_enemy_behind()  # check for overlapping with enemy

            self.draw_explosion()  # draws explosion, if the player has shot an enemy

            self.screen.fill((100, 100, 100)) # update the screen and draw all sprites on new positions

            self.draw_bullet_holes()
            self.enemies.draw(self.screen)
            self.draw_user_drawing()
            self.calculate_barricade()
            self.draw_barricade()

            self.all_sprites.draw(self.screen)

            self.recognize_activity()  # recognize gesture

            # updates info line on top and munition line on bottom of the game canvas
            self.drawInfoLine("Highscore: " + str(self.highscore))
            self.drawMunitionLine(self.munition_counter, self.lives)

            pygame.display.update(self.munition_line.get_rect())
            pygame.display.update(self.info_line_top.get_rect())
            pygame.display.flip()

            self.init_pygame_events()

        else:
            self.clock.tick(60)
            self.screen.fill((100, 100, 100))
            self.switch_draw_shoot_mode()
            font = pygame.font.Font(None, 36)
            self.text = font.render("GAME OVER - Press Home to restart", 1, (10, 10, 10))
            textpos = self.text.get_rect()
            self.screen.blit(self.text, (250, 250))

            pygame.display.flip()
            self.init_pygame_events()

    def switch_draw_shoot_mode(self):
        if self.input_device == "wiimote":
            # handles drawing mode and disables shooting while drawing
            # allows drawing when the A button on the wiimote is pressed

            if self.wm_pointer.buttons['A']:
                cursor_pos = pygame.mouse.get_pos()

                if len(self.drawing_x_values) == 0:
                    self.drawing_x_values.append(cursor_pos[0])
                    self.drawing_y_values.append(cursor_pos[1])
                else:
                    if not self.drawing_x_values[-1] == cursor_pos[0] and not self.drawing_y_values[-1] == cursor_pos[-1]:
                        self.drawing_x_values.append(cursor_pos[0])
                        self.drawing_y_values.append(cursor_pos[1])


                if self.currently_drawing == True:
                    print("Still Drawing")
                else:
                    print("Drawing Started")
                    self.barricade = {}

                self.currently_drawing = True

                return

            elif self.wm_pointer.buttons['Home']:
                self.munition_counter = Constants.MUNITION_COUNT
                self.lives = Constants.MAX_NUM_LIVES
                self.shot_enemy = False
                self.highscore = 0
                #self.level = 1
                self.level_seconds_counter = 0
                self.reload_delay = 5

                self.hit_enemy = None
                self.shooted_enemy = None
                self.shoot_enemy_anim_iterator = 0

                self.game_over = False
                self.restarted = True
                for enemy in self.enemies:
                    self.enemies.remove(enemy)

                for sprite in self.all_sprites:
                    self.all_sprites.remove(sprite)
                self.screen.fill((100, 100, 100))
                self.init_sprites()
                pygame.display.flip()
            else:
                # disables drawing when shooted
                # allows shooting when the B button on the wiimote is pressed
                if self.wm_pointer.buttons['B']:
                    if self.new_click_ok(time.time()):
                        x = pygame.mouse.get_pos()[0]
                        y = pygame.mouse.get_pos()[1]
                        self.player_shoot(x,y)

            if len(self.drawing_x_values) > 0:
                print("Drawing finished!")
                self.gesture_recognizer.recognize_drawing(self.drawing_x_values, self.drawing_y_values)
                self.currently_drawing = False
                self.drawing_x_values = []
                self.drawing_y_values =[]

    def calculate_barricade(self):
        if len(self.drawing_x_values) == 0:
            return

        start_x = self.drawing_x_values[0]
        start_y = self.drawing_y_values[0]
        min_x = min(self.drawing_x_values)
        max_x = max(self.drawing_x_values)
        min_y = min(self.drawing_y_values)
        max_y = max(self.drawing_y_values)

        width = max_x - min_x
        height = max_y - min_y

        if width > self.WIDTH/3 or height > self.HEIGHT/3:
            print("Too big!")
            self.barricade =  {}
            self.display_hint("Too Big!")
            return

        barricade_x = start_x
        barricade_y = start_y

        # If the square has not been drawn starting from the top-left corner, we roughly calculate the pos of the top left corner_
        if abs(start_x-min_x) > abs(start_x-max_x):
            barricade_x = min_x
        if abs(start_y-min_y) > abs(start_y-max_y):
            barricade_y = min_y

        self.barricade = {
            "barricade_x": barricade_x,
            "barricade_y":  barricade_y,
            "width": width,
            "height": height,
            "creation_time": time.time()
        }

    def display_hint(self, hint):
        font = pygame.font.Font(None, 50)
        self.text = font.render(hint, 1, (25, 42, 86))
        self.screen.blit(self.text, (pygame.mouse.get_pos()[0] + 100, pygame.mouse.get_pos()[1]))

    def draw_barricade(self):
        # Destroy barricade after a certain amount of time:
        if "creation_time" in self.barricade and time.time() - self.barricade["creation_time"] > Constants.BARRICADE_LIVETIME:
            self.barricade = {}

        if not self.currently_drawing and "barricade_x" in self.barricade.keys():
            pygame.draw.rect(self.screen,(139,69,19),(self.barricade["barricade_x"], self.barricade["barricade_y"], self.barricade["width"], self.barricade["height"]))


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
        if self.munition_counter > 1:
            self.munition_counter -= 1
            self.play_sound("shot")
            self.bullet_holes.append([x, y])

            # check for each enemy, if the mouse or wiimote, i.e. x and y are within an enemy
            for enemy in self.enemies:
                dist = math.hypot(x - enemy.rect.centerx, y - enemy.rect.centery)
                # needs to be smaller than enemy radius
                if dist <= 50:
                    self.shot_enemy = True
                    self.shooted_enemy = enemy
        else:
            self.play_sound("no_ammo")

    def draw_bullet_holes(self):
        for i in range(len(self.bullet_holes)):
            pygame.draw.circle(self.screen, (50, 50, 50), (self.bullet_holes[i][0], self.bullet_holes[i][1]), Constants.BULLET_HOLE_SIZE)
        if len(self.bullet_holes) > 100:
            del self.bullet_holes[0]

    # checks if the player is overlapped by an enemy
    def check_enemy_behind(self):
        for enemy in self.enemies:
            # is true as soon as the enemy waiting delay is over
            check_for_overlapping = enemy.get_collision()
            if (check_for_overlapping == True):
                enemy.reset()
                self.player.reset()
                if (self.lives > 1):
                    self.lives -= 1
                    self.play_sound("ouch")
                else:
                    if self.restarted == True:
                        self.game_over = False

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
            #self.level += 1
            enemy = Enemy(1, position_arr_x[randint(0, 1)], position_arr_y[randint(0,1)], 1, randint(1,5))
            self.enemies.add(enemy)
        else:
            self.level_seconds_counter +=1


    def draw_user_drawing(self):
        if len(self.drawing_x_values) > 0:
            for i in range(len(self.drawing_x_values) - 1):
                pygame.draw.line(self.screen, (251, 197, 49), [self.drawing_x_values[i], self.drawing_y_values[i]], [self.drawing_x_values[i+1], self.drawing_y_values[i+1]], 10)

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
                    self.munition_counter = Constants.MUNITION_COUNT
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # check for collision with crosshairs and enemy
                x = pygame.mouse.get_pos()[0]
                y = pygame.mouse.get_pos()[1]
                self.player_shoot(x,y)

    def recognize_activity(self):
        if self.wm_pointer:
            accelerometer = self.wm_pointer.accelerometer

            predicted_activity = self.activity_recognizer.predict_activity(accelerometer[0], accelerometer[1], accelerometer[2])
            if predicted_activity == "reload":
                if self.munition_counter == 0:
                    self.play_sound("reload")
                    self.munition_counter = Constants.MUNITION_COUNT


# from http://kidscancode.org/blog/2016/08/pygame_1-2_working-with-sprites/
class Enemy(pygame.sprite.Sprite):
    def __init__(self,  id,x,y,speed,randint):
        # todo: create global constants for width and height and all the other hardcoded numbers
        pygame.sprite.Sprite.__init__(self)
        self.id = id
        self.speed = speed

        # sets the image of the enemy objects
        self.circle_img = pygame.image.load(path.join(Constants.IMG_DIR, str(randint)+".png")).convert()
        self.image = self.circle_img
        # scales down image
        self.image = pygame.transform.scale(self.circle_img, (Constants.ENEMY_SIZE, Constants.ENEMY_SIZE))
        # avoids a black background
        self.image.set_colorkey((250, 250, 250))

        # specifies position of enemy
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.enemy_iterator = 0

        # init
        self.enemy_delay = Constants.ENEMY_DELAY
        self.lose_live = False
        self.explosion_sprite = []
        self.enemy_sprite = []
        self.collisionY = False
        self.collisionX = False

        self.all_enemies = []
        enemy_1 = pygame.image.load(path.join(Constants.IMG_DIR, "1.png")).convert()
        enemy_2 = pygame.image.load(path.join(Constants.IMG_DIR, "2.png")).convert()
        enemy_3 = pygame.image.load(path.join(Constants.IMG_DIR, "3.png")).convert()
        enemy_4 = pygame.image.load(path.join(Constants.IMG_DIR, "4.png")).convert()

        self.all_enemies.append(enemy_1)
        self.all_enemies.append(enemy_2)
        self.all_enemies.append(enemy_3)
        self.all_enemies.append(enemy_4)

        # creates a list of all explosion images
        for x in range(1, 17):
            explode_img_1 = pygame.image.load(path.join(Constants.IMG_DIR, "explosion_" + str(x) + ".png")).convert()
            self.explosion_sprite.append(explode_img_1)

    def explode(self, iterator):
        self.speed = 0 # hinder enemy to move any further if he was shooted
        # sets explosion image to image in list index defined by iterator that is passed in update method
        self.image = pygame.transform.scale(self.explosion_sprite[iterator], (90, 90))
        self.image.set_colorkey((0, 0, 0))

    def get_explosion_duration(self):
        return len(self.explosion_sprite)

    # from https://stackoverflow.com/questions/20044791/how-to-make-an-enemy-follow-the-player-in-pygame
    def move_towards_player(self, Player):
        #if(self.enemy_iterator < len(self.enemy_sprite)-1):

            #self.enemy_iterator += 1
            #print(self.enemy_iterator)
        #else:
            #self.enemy_iterator =0
            #print(self.enemy_iterator)

        #self.image = pygame.transform.scale(self.enemy_sprite[self.enemy_iterator], (90, 90))


        self.image.set_colorkey((0, 0, 0))
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
        self.crosshair_img = pygame.image.load(path.join(Constants.IMG_DIR, "circle-5.png")).convert()
        self.WIDTH = pygame.display.get_surface().get_width()
        self.HEIGHT = pygame.display.get_surface().get_height()
        self.image = self.crosshair_img
        self.image = pygame.transform.scale(self.crosshair_img, (Constants.CROSSHAIR_SIZE, Constants.CROSSHAIR_SIZE))
        self.image.set_colorkey((0,0,0))
        self.radius = 10
        self.rect = self.image.get_rect()

        # Make Mouse Cursor invisible
        pygame.mouse.set_cursor((8,8),(0,0),(0,0,0,0,0,0,0,0),(0,0,0,0,0,0,0,0))

    # display crosshairs on mouse position
    def update(self):
        mousex, mousey = pygame.mouse.get_pos()
        self.rect.centerx = mousex
        self.rect.centery = mousey


class ActivityRecognizer:

    def __init__(self):
        print("Init Activity Recognizer")
        self.category_list = []
        self.ready_for_prediction = False
        self.c = svm.SVC()
        self.prediction_values = [[], [], []]
        self.minlen = 1000  # Just a large value to begin with

        self.read_data_from_csv()

    def get_categories(self):
        csv_files = glob.glob(path.join("activity_templates", "*.csv"))  # get all csv files from the directory
        for file in csv_files:
            # split file at _ character, so that only the name without id is returned
            category = file.split("/")[1]
            category = category.split("_")[0]
            if category not in self.category_list:
                self.category_list.append(category)
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

        csv_files = glob.glob(path.join("activity_templates", "*.csv"))
        if len(csv_files) == 0:
            print("No CSV Files to train with!")
            return

        for csv_file in csv_files:
            category_name = csv_file.split("/")[1]
            category_name = category_name.split("_")[0]
            for activity_name, value in activities.items():
                if activity_name == category_name:
                    activities[activity_name].append([])
                    for line in open(csv_file, "r").readlines():
                        x, y, z = map(int, line.strip().split(","))
                        mean = (x + y + z) / 3
                        activities[activity_name][len(activities[activity_name]) - 1].append(mean)

        self.cut_off_data(activities)

    def cut_off_data(self, activities):
        #self.minlen = 10000000  # Large number to begin
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
        self.ready_for_prediction = True
        print("Training finished!")

    def predict_activity(self, x, y, z):

        if self.ready_for_prediction:
            if len(self.prediction_values[0]) < self.minlen:
                self.prediction_values[0].append(x)
                self.prediction_values[1].append(y)
                self.prediction_values[2].append(z)
                #return self.last_prediction
                return ""
            else:
                avg = []
                for i in range(len(self.prediction_values[0])):
                    avg.append((self.prediction_values[0][i] + self.prediction_values[1][i] +
                                self.prediction_values[2][i]) / 3)

                self.prediction_values = [[], [], []]

                # This line is taken from the "Wiimote - FFT - SVM" notebook from Grips
                freq = [np.abs(fft(avg) / len(avg))[1:len(avg) // 2]]
                #self.last_prediction = str(self.c.predict(freq)[0])
                #return self.last_prediction
                print(str(self.c.predict(freq)[0]))
                return str(self.c.predict(freq)[0])


"""
This class implements the $1 gesture recognizer from the paper: Wobbrock, J.O., Wilson, A.D. and Li, Y. (2007).
Gestures without libraries, toolkits or training: A $1 recognizer for user interface prototypes.
"""
class GestureRecognizer:

    def __init__(self):
        self.N = 64  # num of points after resampling
        self.SIZE = 100  # Size of bounding box
        # Code taken from https://stackoverflow.com/questions/25212181/is-the-golden-ratio-defined-in-python
        self.PHI = (1 + 5 ** 0.5) / 2
        # Treshold according to the paper is 2° (p.5)
        self.TRESHOLD = 2

        self.templates = []
        self.template_names = []
        self.load_templates()


    def recognize_drawing(self, drawing_x_coordinates, drawing_y_coordinates):

        if len(drawing_x_coordinates) < 4:  # Skip recognition if not enough points are drawn (so no error shows)
            return

        points = []

        for i in range(len(drawing_x_coordinates)):
            points.append([drawing_x_coordinates[i], drawing_y_coordinates[i]])

        resampled_points = self.resample(points, self.N)
        rotated_points = self.rotate_to_zero(resampled_points)
        scaled_points = self.scale_to_square(rotated_points, self.SIZE)
        points_for_recognition = self.translate_to_origin(scaled_points)

        recgonize = self.recognize(points_for_recognition, self.templates)

        return "Test"

    # get all templates that are stored as data values within csv files
    def load_templates(self):
        csv_files = glob.glob(path.join("drawing_templates", "*.csv"))  # get all csv files from the directory

        for file in csv_files:
            # split file at ".", so that only the name without ".csv" is returned
            filename = file.split(".")[0]
            self.template_names.append(filename)
            template = []

            with open(file) as csvfile:
                readcsv = csv.reader(csvfile, delimiter=',')
                for row in readcsv:
                    # get content of csv and store it in template list
                    template.append([float(row[0]), float(row[1])])
            self.templates.append(template)

    # Done according to the pseudo-code from the paper "Wobbrock, J.O., Wilson, A.D. and Li, Y. (2007).
    # Gestures without libraries, toolkits or training: A $1 recognizer for user interface prototypes."
    def resample(self, points, n):
        increment = self.path_length(points) / (n-1)  # Increment I
        D = 0

        new_points = [points[0]]

        i = 1
        j = len(points)

        # iterate over all points of a gesture
        while i < j:
            d = self.distance(points[i-1], points[i])

            if (D + d) >= increment:
                qx = points[i-1][0] + ((increment - D) / d) * (points[i][0] - points[i-1][0])
                qy = points[i-1][1] + ((increment - D) / d) * (points[i][1] - points[i-1][1])

                new_points.append([qx, qy])
                # Insert into list: https://www.tutorialspoint.com/python/list_insert.htm
                points.insert(i, [qx, qy])
                D = 0
            else:
                D += d

            j = len(points)
            i += 1
        # This part is implemented like here: https://depts.washington.edu/madlab/proj/dollar/dollar.js
        # handle issue, if there are less points than n
        if len(new_points) == (n - 1):
            new_points.append([points[len(points) - 1][0], points[len(points) - 1][1]])

        return new_points

    # According to the paper: Find the gestures indicative angle (the angle formed between the centroid
    # of the gesture and the gestures first point). Then rotate the gesture so the angle is at 0°
    def rotate_to_zero(self, points):
        c = self.centroid(points)
        # Atan2 is needed (see: https://depts.washington.edu/madlab/proj/dollar/dollar.js)
        theta = math.atan2(c[1] - points[0][1], c[0] - points[0][0])
        new_points = self.rotate_by(points, math.radians(-theta))
        return new_points

    def rotate_by(self, points, angle):
        c = self.centroid(points)

        new_points = []
        cos = math.cos(angle)
        sin = math.sin(angle)
        # create list of rotated points
        for point in points:
            qx = (point[0] - c[0]) * cos - (point[1] - c[1]) * sin + c[0]
            qy = (point[0] - c[0]) * sin - (point[1] - c[1]) * cos + c[0]
            new_points.append([qx, qy])

        return new_points

    # scale down all points so that they fit in a bounding box with a fixed size
    def scale_to_square(self, points, size):
        B = self.bounding_box(points)

        new_points = []

        for point in points:
            qx = point[0] * (size / B[0])
            qy = point[1] * (size / B[1])
            new_points.append([qx, qy])

        return new_points

    # moves points to the origin
    def translate_to_origin(self, points):
        c = self.centroid(points)

        new_points = []

        for point in points:
            qx = point[0] - c[0]
            qy = point[1] - c[1]
            new_points.append([qx, qy])

        return new_points

    # predicts the entered gesture
    def recognize(self, points, templates):

        b = math.inf

        self.best_find = self.template_names[0]
        # iterate over all templates and check, which of them has the smallest distance to the entered gesture
        for i in range(len(templates)):
            d = self.distance_at_best_angle(points, templates[i], -math.radians(45), math.radians(45), 2)
            print("Distance of " + self.template_names[i] + ": " + str(d))
            if d < b:
                b = d
                self.best_find = self.template_names[i]

        score = 1 - b / 0.5 * math.sqrt(self.SIZE**2 + self.SIZE**2)
        print("Score: " + str(score))
        print("Best find: " + self.best_find)
        return [self.best_find, score]

    # Function implemented like here: https://depts.washington.edu/madlab/proj/dollar/dollar.js
    # get the minimal matching distance between a template and a gesture
    def distance_at_best_angle(self, points, template, a, b, treshold):
        x1 = self.PHI * a + (1 - self.PHI) * b

        f1 = self.distance_at_angle(points, template, x1)
        x2 = (1 - self.PHI) * a + self.PHI * b

        f2 = self.distance_at_angle(points, template, x2)

        while abs(b - a) > treshold:
            if f1 < f2:
                b = x2
                x2 = x1
                f2 = f1
                x1 = self.PHI * a + (1 - self.PHI) * b
                f1 = self.distance_at_angle(points, template, x1)
            else:
                a = x1
                x1 = x2
                f1 = f2
                x2 = (1 - self.PHI) * a + self.PHI * b
                f2 = self.distance_at_angle(points, template, x2)

        return max(f1, f2)

    # returns the distance of rotated points in comparison to a template
    def distance_at_angle(self, points, template, angle):
        new_points = self.rotate_by(points, angle)
        return self.path_distance(new_points, template)

    # calculates the path between two points
    def path_distance(self, A, B):
        d = 0
        for i in range(len(A)):
            d += self.distance(A[i], B[i])
        return d / len(A)

    # Function implemented like here: https://depts.washington.edu/madlab/proj/dollar/dollar.js
    # calculates the bounding box
    def bounding_box(self, points):

        min_x = math.inf
        max_x = -math.inf
        min_y = math.inf
        max_y = -math.inf

        for point in points:
            if point[0] < min_x:
                min_x = point[0]
            if point[0] > max_x:
                max_x = point[0]

            if point[1] < min_y:
                min_y = point[1]
            if point[1] > max_y:
                max_y = point[1]

        width = max_x - min_x
        height = max_y - min_y
        return [width, height]

    # Function implemented like here: https://depts.washington.edu/madlab/proj/dollar/dollar.js
    # returns the centroid values of a given set of points
    def centroid(self, points):
        x = 0
        y = 0

        for i in range(len(points)):
            x = x + points[i][0]
            y = y + points[i][1]

        x = x / len(points)
        y = y / len(points)

        return [x, y]

    # Done according to the pseudo-code from the paper "Wobbrock, J.O., Wilson, A.D. and Li, Y. (2007).
    # Gestures without libraries, toolkits or training: A $1 recognizer for user interface prototypes."
    # calculates the length of a path of points
    def path_length(self, points):
        d = 0

        for i in range(1, len(points)):
            d += self.distance(points[i-1], points[i])

        print("Length: " + str(d))
        return d

    # Done with Pythagoras c = sqrt((xA-xB)² + (yA-yB)²)
    # calculate the distance between two points
    def distance(self, point_one, point_two):
        return math.sqrt((point_two[0] - point_one[0])**2 + (point_two[1] - point_one[1])**2)


"""
This class gets the coordinates of four LEDs as input params and calculates the coordinates of point the player 
is pointing at.
"""
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
        try:
            source_to_unit = np.linalg.inv(unit_to_source)
        except np.linalg.linalg.LinAlgError:
            return 0,0

        # Step 5: Compute the combined matrix
        source_to_dest = unit_to_dest @ source_to_unit

        # Step 6: To map a location  (x,y)  from the source image to its corresponding location in the destination image, compute the product
        x,y,z = [float(w) for w in (source_to_dest @ np.matrix([[512], [384], [1]]))]

        # step 7: dehomogenization
        x = int(x / z)
        y = int(y / z)

        return x, y


"""
This class gets the coordinates of the two LEDs of the head tracking device as input and calculates the position of 
the player on the screen.
"""
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
        # Temp: Invert x
        x_on_screen = self.WIDTH - x_on_screen
        print("X on screen: ", x_on_screen)
        print("Y on screen: ", y_on_screen)
        return x_on_screen, y_on_screen


def main():
    #app = QtWidgets.QApplication(sys.argv)
    wiimote_game = WiimoteGame()
    #sys.exit(app.exec_())
    sys.exit()


if __name__ == '__main__':
    main()
