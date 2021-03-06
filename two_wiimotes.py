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
    # Bullet hole: created by Vitus using a texture from https://opengameart.org/content/broken-glass
                   created by Cookie (CC BY 3.0)
    # Forest Background: https://opengameart.org/content/forest-background (CC0 1.0)

    Sounds:
    # Background Music: Stellar Forest by InSintesi https://freesound.org/people/InSintesi/sounds/369237/ (CC BY 3.0)
    # Sound "shot.wav": https://freesound.org/people/LeMudCrab/sounds/163455/ (CC0 1.0)
    # Sound "reload.wav": https://freesound.org/people/IchBinJager/sounds/272068/ by IchBinJager (CC BY 3.0)
    # Sound "ouch.wav": https://freesound.org/people/girlhurl/sounds/339162/ (CC0 1.0)
    # Sound "no_ammo.wav": https://freesound.org/people/knova/sounds/170272/ by knova (CC BY-NC 3.0)
    # Sound "game_over.wav": https://freesound.org/people/noirenex/sounds/159408/ (CC0 1.0)
"""


# Pygame needs to be initialized at the beginning
pygame.init()


"""
For easy access to constants from all classes, they have been put into their own class.
"""


class Constants:
    WIIMOTE_TRACKER_ADDRESS = "B8:AE:6E:55:B5:0F"  # MAC Address of the "Tracker" Wiimote
    WIIMOTE_POINTER_ADDRESS = "B8:AE:6E:1B:5B:03"  # MAC Address of the "Pointer" Wiimote

    WIIMOTE_IR_CAM_WIDTH = 1024  # Horizontal resolution of the Wiimote IR Camera
    WIIMOTE_IR_CAM_HEIGHT = 768  # Vertical Resolution of the Wiimote IR Camera

    # Center coordinates of the Wiimote IR Camera
    WIIMOTE_IR_CAM_CENTER = (WIIMOTE_IR_CAM_WIDTH/2, WIIMOTE_IR_CAM_HEIGHT/2)

    FPS = 60  # Target FPS of the game
    ENEMY_DELAY = 30  # Steps before an enemy can hit a player
    DURATION_BETWEEN_ENEMIES = 150  # Steps between enemy spawns
    CROSSHAIR_SIZE = 100  # Size in pixel of the Crosshair
    MOVING_AVERAGE_NUM_VALUES = 5  # num of values that should be buffered for moving average filter

    # The tracking of the head needs to be inverted if the tracking wiimote is behind and not in front of the player
    INVERT_HEAD_TRACKING_LEFT_RIGHT = True

    ENEMY_SIZE = 100  # Size of the enemies in pixel
    BULLET_HOLE_SIZE = 50  # Size of the bullet holes on screen in pixel
    BARRICADE_LIFETIME = 5  # Lifetime of a barricade in seconds
    MUNITION_COUNT = 10  # Num shots after reload
    MAX_NUM_LIVES = 5  # Lifes at beginning of the game
    TIME_BETWEEN_SHOTS = 0.5  # Time in seconds between the player can fire another bullet.
    NAME_INPUT_SCROLL_SPEED = 0.1  # Speed of the cursor movement while entering the player name

    DRAWING_COLOR = (251, 197, 49)  # Color for drawing the line of the barricade
    GAME_OVER_SCREEN_COLOR = (100, 100, 100)  # Background color of the Game Over Screen
    BARRICADE_COLOR = (251, 197, 49)  # Color of the barricade
    HINT_COLOR = (251, 197, 49)  # Text Color of displaying hints

    SCREEN = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)  # The pygame screen object
    WIDTH = pygame.display.get_surface().get_width()  # Horizontal resolution of the display
    HEIGHT = pygame.display.get_surface().get_height()  # Vertical resolution of the display

    MAX_BARRICADE_WIDTH = WIDTH/2  # Max width of a barricade a user can draw
    MAX_BARRICADE_HEIGHT = HEIGHT/2  # Max hight of a barricade a user can draw

    # Letters allowed for entering a name for the highscore
    NAME_INPUT_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R",
                          "S", "T", "U", "V", "W", "X", "Y", "Z", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "_"]

    IMG_DIR = path.join(path.dirname(__file__), 'img')  # defines the directory where all images are located

    # Images used in the game:
    GAME_BACKGROUND_LAYER_1 = \
        pygame.transform.scale(pygame.image.load(path.join(IMG_DIR, "parallax-forest-back-trees.png")),
                               (WIDTH, HEIGHT)).convert()
    GAME_BACKGROUND_LAYER_2 = \
        pygame.transform.scale(pygame.image.load(path.join(IMG_DIR, "parallax-forest-middle-trees.png")),
                               (WIDTH + 100, HEIGHT)).convert_alpha()
    GAME_BACKGROUND_LAYER_3 = \
        pygame.transform.scale(pygame.image.load(path.join(IMG_DIR, "parallax-forest-front-trees.png")),
                               (WIDTH + 100, HEIGHT)).convert_alpha()
    CROSSHAIR_IMAGE = pygame.image.load(path.join(IMG_DIR, "circle-5.png")).convert()
    BULLET_HOLE_IMAGE = pygame.image.load(path.join(IMG_DIR, "bullet_hole.png")).convert_alpha()
    BULLET_IMAGE = pygame.image.load(path.join(IMG_DIR, "bullet.png"))
    HEART_IMAGE = pygame.image.load(path.join(IMG_DIR, "heart.png"))


class WiimoteGame:

    def __init__(self):
        super().__init__()

        self.gesture_recognizer = GestureRecognizer()
        self.activity_recognizer = ActivityRecognizer()

        # Buffered values:
        self.pointer_x_values = []
        self.pointer_y_values = []
        self.drawing_x_values = []
        self.drawing_y_values = []

        self.currently_drawing = False  # Flag: Is player drawind
        self.drawing_ok = False  # Has the barricade been recognized as a square by the $1 Gesture recognizer

        self.barricade = {}  # Contains the current barricade, if one exists

        self.enemies_at_once = 1  # How many enemies can spawn right now
        self.enemies_incrementor = 0

        self.bullet_holes = []  # The locations of all bullet holes are saved here

        self.player_name = ["A", "A", "A", "A", "A"]  # Letters the player typed in on the Game Over screen
        self.name_input_pos = 0  # Pos of the cursor while entering the player name

        self.sounds = {}  # A dictionnary containing all sound files
        self.input_device = "wiimote"  # Can be set to mouse for debug purposes
        self.last_button_press = time.time()  # Time stamp of the last button press

        self.init_pygame()
        self.connect_wiimotes()

    # Init pygame components
    def init_pygame(self):
        self.init_canvas()
        self.init_sprites()
        self.clock = pygame.time.Clock()
        self.init_sounds()

    # sets up game canvas (Main canvas and the two HUD lines)
    def init_canvas(self):
        self.drawInfoLine("Highscore: 0")
        self.drawGameCanvas()
        self.drawMunitionLine(Constants.MUNITION_COUNT, Constants.MAX_NUM_LIVES)

    # draws the upper line that displays the highscore on the screen
    def drawInfoLine(self, text):
        self.info_line_top = pygame.Surface((Constants.WIDTH, 50))
        self.info_line_top = self.info_line_top.convert()
        self.info_line_top.fill((250, 250, 250))
        font = pygame.font.Font(None, 50)
        self.text = font.render(text, 1, (10, 10, 10))
        textpos = self.text.get_rect()
        textpos.centerx = self.info_line_top.get_rect().centerx
        self.info_line_top.blit(self.text, textpos)
        Constants.SCREEN.blit(self.info_line_top, (0, 0))

    # draws the main game canvas
    def drawGameCanvas(self):
        self.game_canvas = pygame.Surface((Constants.WIDTH, Constants.HEIGHT))
        Constants.SCREEN.blit(self.game_canvas, (0, 50))

    # draws the lower line on the canvas that displays the munition and lives of the player
    def drawMunitionLine(self, num_bullets, lives):
        self.munition_line = pygame.Surface((Constants.WIDTH, 50))
        self.munition_line.fill((250, 250, 250))
        Constants.SCREEN.blit(self.munition_line, (0, Constants.HEIGHT - 50))

        bullet = Constants.BULLET_IMAGE  # Draw bullets on screen
        for i in range(num_bullets):
            Constants.SCREEN.blit(bullet, (Constants.WIDTH - i*20 - 20, Constants.HEIGHT - 50, 100, 100))

        heart = Constants.HEART_IMAGE  # Draw hearts on screen
        for i in range(lives):
            Constants.SCREEN.blit(heart, (i*50 + 10, Constants.HEIGHT - 40, 100, 100))

    # adds all sprites, i.e. game elements to the screen
    def init_sprites(self):
        self.all_sprites = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.players = pygame.sprite.Group()
        enemy = Enemy(1, 0, 0, 1, randint(1, 5))
        self.enemies.add(enemy)

        self.crosshairs = Crosshairs()
        self.all_sprites.add(self.crosshairs)
        self.player = Player()
        self.players.add(self.player)
        self.all_sprites.add(self.player)
        self.enemies.draw(Constants.SCREEN)
        self.all_sprites.draw(Constants.SCREEN)

    # Load sound files and save them to a dictionary
    def init_sounds(self):
        try:
            self.sounds = {
                "shot": pygame.mixer.Sound(path.join("sounds", "shot.wav")),
                "reload": pygame.mixer.Sound(path.join("sounds", "reload.wav")),
                "ouch": pygame.mixer.Sound(path.join("sounds", "ouch.wav")),
                "no_ammo": pygame.mixer.Sound(path.join("sounds", "no_ammo.wav")),
                "game_over": pygame.mixer.Sound(path.join("sounds", "game_over.wav"))
            }
            pygame.mixer.music.load(path.join("sounds", "background_music_forest.wav"))
        except pygame.error:  # Catch error if audio files are missing
            sys.exit()

    # Start playing the background music
    def play_music(self):
        pygame.mixer.music.play()

    # Stop playing the background music
    def stop_music(self):
        pygame.mixer.music.stop()

    # Play a sound saved in the sounds dictionary
    def play_sound(self, sound_name):
        sound = self.sounds[sound_name]
        sound.play()

    # Start the pairing process, done like in wiimote_demo.py
    def connect_wiimotes(self):

        tracker = Constants.WIIMOTE_TRACKER_ADDRESS
        pointer = Constants.WIIMOTE_POINTER_ADDRESS

        self.tracking = Tracking()
        self.pointing = Pointing()

        # mode with bluetooth MAC adresses on stdin, 2 adresses should be passed
        if len(sys.argv) == 3:
            tracker = sys.argv[1]
            pointer = sys.argv[2]

        self.wm_tracker = wiimote.connect(tracker, None)
        self.wm_tracker.ir.register_callback(self.get_ir_data_of_tracker)
        self.wm_tracker.leds = [0, 1, 0, 0]

        self.wm_pointer = wiimote.connect(pointer, None)
        self.wm_pointer.ir.register_callback(self.get_ir_data_of_pointer)
        self.wm_pointer.leds = [1, 0, 0, 0]

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

            x, y = self.pointing.process_ir_data(led_one, led_two, led_three, led_four)

            # Collect values in list
            self.pointer_x_values.append(x)
            self.pointer_y_values.append(y)

            # Filter values using the moving average filter
            if len(self.pointer_x_values) == Constants.MOVING_AVERAGE_NUM_VALUES:
                filtered_x, filtered_y = self.moving_average(self.pointer_x_values, self.pointer_y_values)
                self.pointer_x_values = []
                self.pointer_y_values = []
                # Only update the cursor if it is on the screen
                if filtered_x >= 0 and filtered_x <= Constants.WIDTH and \
                        filtered_y >= 0 and filtered_y <= Constants.HEIGHT:
                    pygame.mouse.set_pos([filtered_x, filtered_y])

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
        if len(ir_data) == 2:  # Looking for the two LEDs of the helmet

            # Check if the Wiimote is outputting wrong values. (If IR is not working, x and y values will be 1023)
            if ir_data[0]["x"] == 1023 and ir_data[0]["x"] == 1023:
                return

            left = (ir_data[0]["x"], ir_data[0]["y"])
            right = (ir_data[1]["x"], ir_data[1]["y"])
            x_on_screen, y_on_screen = self.tracking.process_ir_data_two_leds(left, right)

            # Only update the player pos if he is on the screen
            if x_on_screen >= 0 and x_on_screen <= Constants.WIDTH and x_on_screen >= 0 \
                    and x_on_screen <= Constants.HEIGHT:
                # Pass the coordinates to the player.
                self.player.set_player_coordinates(x_on_screen, y_on_screen)

    # Starting the game loop
    def start_loop(self):
        self.reset_game()
        loop_running = True
        while loop_running:
            self.loop_iteration()

    # resets game after game over
    def reset_game(self):
        self.munition_counter = Constants.MUNITION_COUNT
        self.lives = Constants.MAX_NUM_LIVES
        self.highscore = 0
        self.shot_enemy = False
        self.level_seconds_counter = 0
        self.hit_enemy = None
        self.shooted_enemy = None
        self.game_over = False
        self.shoot_enemy_anim_iterator = 0
        self.bullet_holes = []
        self.play_music()

        for enemy in self.enemies:
            self.enemies.remove(enemy)

        for sprite in self.all_sprites:
            self.all_sprites.remove(sprite)

        self.init_sprites()

    # One iteration of the loop: 1/60 sec
    def loop_iteration(self):

        self.clock.tick(Constants.FPS)
        self.check_wiimote_input()

        if not self.game_over:
            self.update_game_logic()
            self.draw_game_elements()

            self.recognize_activity()  # recognize gesture. Looks for reload of gun
            self.drawInfoLine("Score: " + str(self.highscore))  # Update displayed Score
            self.drawMunitionLine(self.munition_counter, self.lives)  # Update Lifes and Ammo
        else:
            self.display_game_over_screen()

        pygame.display.flip()  # Update the display
        self.init_pygame_events()

    # Player and enemy movement, collision detection, etc.
    def update_game_logic(self):
        self.draw_background_images()

        self.check_level()

        # updates the enemies and moves them
        self.enemies.update()
        self.all_sprites.update()

        # enemy should follow the player
        for enemy in self.enemies:
            enemy.move_towards_player(self.player)

        self.calculate_barricade()
        self.check_enemy_behind()  # check for overlapping with enemy

    # Draw updated game elements onto the screen
    def draw_game_elements(self):
        self.enemies.draw(Constants.SCREEN)
        self.draw_user_drawing()
        self.draw_barricade()
        self.draw_bullet_holes()
        self.draw_explosion()
        self.all_sprites.draw(Constants.SCREEN)

    # Draws the background on the screen. It is composed of three images. Depending on the movement of the head,
    # the two layers of the trees get moved accordingly, to create some sort of a small 3D effect.
    def draw_background_images(self):
        Constants.SCREEN.blit(Constants.GAME_BACKGROUND_LAYER_1, (0, 0))
        Constants.SCREEN.blit(Constants.GAME_BACKGROUND_LAYER_2, (-(self.player.get_player_coordinates()[0]
                                                                    - Constants.WIDTH/2)/100 - 50,
                                                                  -(self.player.get_player_coordinates()[1]
                                                                    - Constants.HEIGHT/2)/100))
        Constants.SCREEN.blit(Constants.GAME_BACKGROUND_LAYER_3, (-(self.player.get_player_coordinates()[0]
                                                                    - Constants.WIDTH/2)/50 - 50,
                                                                  -(self.player.get_player_coordinates()[1]
                                                                    - Constants.HEIGHT/2)/50))

    # Show the game over screen if necessary
    def display_game_over_screen(self):
        Constants.SCREEN.fill(Constants.GAME_OVER_SCREEN_COLOR)
        self.draw_game_over_text()
        self.draw_name_input()
        self.draw_highscore()

    def draw_game_over_text(self):
        font = pygame.font.Font(None, 100)
        game_over_message = font.render("GAME OVER!", 1, (255, 255, 255))
        Constants.SCREEN.blit(game_over_message, game_over_message.get_rect(center=(Constants.WIDTH/2,
                                                                                    1/10 * Constants.HEIGHT)))

        font = pygame.font.Font(None, 36)
        highscore_message = font.render("Your Score is " + str(self.highscore), 1, (255, 255, 255))
        restart_message = font.render("Type in your name using the Wiimote D-Pad", 1, (255, 255, 255))
        save_message = font.render("Press 'Home' to restart", 1, (255, 255, 255), (100, 100, 100))
        Constants.SCREEN.blit(highscore_message, highscore_message.get_rect(center=(Constants.WIDTH/2,
                                                                                    2/10 * Constants.HEIGHT)))
        Constants.SCREEN.blit(restart_message, restart_message.get_rect(center=(Constants.WIDTH/2,
                                                                                3/10 * Constants.HEIGHT)))
        Constants.SCREEN.blit(save_message, save_message.get_rect(center=(Constants.WIDTH/2,
                                                                          4/10 * Constants.HEIGHT)))

    # Display the UI that allows a user to enter a name
    def draw_name_input(self):
        font = pygame.font.Font(None, 200)

        letter_font_objects = []

        # Draw each of the five letters on by one, using the chars from the "self.playername" list
        for i in range(len(self.player_name)):
            if self.name_input_pos == i:
                letter_font_objects.append(font.render(self.player_name[i], 1, (255, 0, 0)))
            else:
                letter_font_objects.append(font.render(self.player_name[i], 1, (255, 255, 255)))

        Constants.SCREEN.blit(letter_font_objects[0], letter_font_objects[0].get_rect(center=(Constants.WIDTH/2 - 400,
                                                                                              Constants.HEIGHT/2)))
        Constants.SCREEN.blit(letter_font_objects[1], letter_font_objects[1].get_rect(center=(Constants.WIDTH/2 - 200,
                                                                                              Constants.HEIGHT/2)))
        Constants.SCREEN.blit(letter_font_objects[2], letter_font_objects[2].get_rect(center=(Constants.WIDTH/2,
                                                                                              Constants.HEIGHT/2)))
        Constants.SCREEN.blit(letter_font_objects[3], letter_font_objects[3].get_rect(center=(Constants.WIDTH/2 + 200,
                                                                                              Constants.HEIGHT/2)))
        Constants.SCREEN.blit(letter_font_objects[4], letter_font_objects[4].get_rect(center=(Constants.WIDTH/2 + 400,
                                                                                              Constants.HEIGHT/2)))

    # Display the top 10 entries of the highscore on the screen
    def draw_highscore(self):
        highscore = Highscore().get_highscore()

        font = pygame.font.Font(None, 30)
        highscore_title = font.render("HIGHSCORE", 1, (255, 255, 255), (100, 100, 100))
        Constants.SCREEN.blit(highscore_title, highscore_title.get_rect(center=(Constants.WIDTH/2,
                                                                                7/10 * Constants.HEIGHT - 40)))
        for i in range(len(highscore)):
            highscore_entry = font.render(str(highscore[i][0]) + ": " + str(highscore[i][1]), 1, (255, 255, 255),
                                          (100, 100, 100))
            Constants.SCREEN.blit(highscore_entry, highscore_entry.get_rect(center=(Constants.WIDTH/2,
                                                                                    7/10 * Constants.HEIGHT
                                                                                    + (i * 20))))

    # Check for Wiimote button input (only on the pointer wiimote)
    def check_wiimote_input(self):
        if self.wm_pointer.buttons['A']:
            self.on_wiimote_a_pressed()
        elif self.wm_pointer.buttons['B']:
            self.on_wiimote_b_pressed()
        elif self.wm_pointer.buttons['Home']:
            self.on_wiimote_home_pressed()
        elif self.wm_pointer.buttons['Up']:
            self.on_wiimote_dpad_pressed('Up')
        elif self.wm_pointer.buttons['Down']:
            self.on_wiimote_dpad_pressed('Down')
        elif self.wm_pointer.buttons['Left']:
            self.on_wiimote_dpad_pressed('Left')
        elif self.wm_pointer.buttons['Right']:
            self.on_wiimote_dpad_pressed('Right')

        # Check if user finished drawing on the screen
        if not self.wm_pointer.buttons['A'] and len(self.drawing_x_values) > 0:
            self.currently_drawing = False
            self.drawing_ok = self.gesture_recognizer.recognize_drawing(self.drawing_x_values, self.drawing_y_values)
            self.currently_drawing = False
            self.drawing_x_values = []
            self.drawing_y_values = []

    # If the user pressed the A button, deal with the painting game logic
    def on_wiimote_a_pressed(self):
        if not self.game_over:
            cursor_pos = pygame.mouse.get_pos()

            if len(self.drawing_x_values) == 0:
                self.drawing_x_values.append(cursor_pos[0])
                self.drawing_y_values.append(cursor_pos[1])
            else:
                if not self.drawing_x_values[-1] == cursor_pos[0] and not self.drawing_y_values[-1] == cursor_pos[-1]:
                    self.drawing_x_values.append(cursor_pos[0])
                    self.drawing_y_values.append(cursor_pos[1])

            if not self.currently_drawing:  # Drawing started if landed here
                self.barricade = {}

            self.currently_drawing = True

    # If the player pressed the B button, fire one shot if amminition is available
    def on_wiimote_b_pressed(self):
        if not self.game_over and self.new_click_ok(time.time(), Constants.TIME_BETWEEN_SHOTS):
            self.last_button_press = time.time()
            self.player_shoot(pygame.mouse.get_pos()[0], pygame.mouse.get_pos()[1])

    # Restart the game if a user pressed the home button
    def on_wiimote_home_pressed(self):
        if self.new_click_ok(time.time(), Constants.TIME_BETWEEN_SHOTS):
            self.last_button_press = time.time()
            playername = ""
            for i in range(len(self.player_name)):
                char = self.player_name[i]
                playername += char

            Highscore().update_highscore(playername, self.highscore)
            self.reset_game()

    # On the Game over screen, the user can navigate through the name input using the d-pad
    def on_wiimote_dpad_pressed(self, dir):
        if self.new_click_ok(time.time(), Constants.NAME_INPUT_SCROLL_SPEED):
            self.last_button_press = time.time()
            if dir == "Up":
                index = Constants.NAME_INPUT_LETTERS.index(self.player_name[self.name_input_pos])
                if (index + 1) > len(Constants.NAME_INPUT_LETTERS) - 1:
                    self.player_name[self.name_input_pos] = Constants.NAME_INPUT_LETTERS[0]
                else:
                    self.player_name[self.name_input_pos] = Constants.NAME_INPUT_LETTERS[index + 1]
            elif dir == "Down":
                index = Constants.NAME_INPUT_LETTERS.index(self.player_name[self.name_input_pos])
                if (index - 1) < 0:
                    self.player_name[self.name_input_pos] = \
                        Constants.NAME_INPUT_LETTERS[len(Constants.NAME_INPUT_LETTERS)-1]
                else:
                    self.player_name[self.name_input_pos] = Constants.NAME_INPUT_LETTERS[index - 1]
            elif dir == "Left":
                if (self.name_input_pos - 1) < 0:
                    self.name_input_pos = len(self.player_name) - 1
                else:
                    self.name_input_pos -= 1
            elif dir == "Right":
                if (self.name_input_pos + 1) > len(self.player_name) - 1:
                    self.name_input_pos = 0
                else:
                    self.name_input_pos += 1

    # Checks if coordinates from a user drawing exist and calculates the size and pos of the barricade accordingly
    def calculate_barricade(self):
        if len(self.drawing_x_values) == 0:
            return

        start_x = self.drawing_x_values[0]  # Start pos is the first point from the drawing coordinates
        start_y = self.drawing_y_values[0]
        min_x = min(self.drawing_x_values)
        max_x = max(self.drawing_x_values)
        min_y = min(self.drawing_y_values)
        max_y = max(self.drawing_y_values)

        width = max_x - min_x
        height = max_y - min_y

        # Notify the user if he wants to draw a barricade is too large (it should not block the entire screen)
        if width > Constants.MAX_BARRICADE_WIDTH or height > Constants.MAX_BARRICADE_HEIGHT:
            self.barricade = {}
            self.display_hint("Too Big!")
            return

        barricade_x = start_x
        barricade_y = start_y

        # If the square has not been drawn starting from the top-left corner, we roughly calculate the pos of the top
        # left corner. This is needed because pygame needs that corner as an input for drawing a square
        if abs(start_x-min_x) > abs(start_x-max_x):
            barricade_x = min_x
        if abs(start_y-min_y) > abs(start_y-max_y):
            barricade_y = min_y

        if self.drawing_ok:
            self.barricade = {
                "barricade_x": barricade_x,
                "barricade_y":  barricade_y,
                "width": width,
                "height": height,
                "creation_time": time.time()
            }

    #  Display a hint on the screen (e.g. if the drawing is too big)
    def display_hint(self, hint):
        font = pygame.font.Font(None, 50)
        self.text = font.render(hint, 1, Constants.HINT_COLOR)
        Constants.SCREEN.blit(self.text, (pygame.mouse.get_pos()[0] + 100, pygame.mouse.get_pos()[1]))

    # Draw the barricade on the screen
    def draw_barricade(self):
        # Destroy barricade after a certain amount of time:
        if "creation_time" in self.barricade and time.time() - self.barricade["creation_time"] \
                > Constants.BARRICADE_LIFETIME:
            self.barricade = {}
            self.drawing_ok = False

        if not self.currently_drawing and "barricade_x" in self.barricade.keys():
            pygame.draw.rect(Constants.SCREEN, Constants.BARRICADE_COLOR, (self.barricade["barricade_x"],
                                                                           self.barricade["barricade_y"],
                                                                           self.barricade["width"],
                                                                           self.barricade["height"]))

    # Check if a button press on the wiimote has happened within the defined time frame
    # This prevents a single button click from beeing interpreted as multiple.
    def new_click_ok(self, current_time, time_to_last_click):
        if current_time - self.last_button_press > time_to_last_click:
            return True
        else:
            return False

    # if the player presses the B button, we check if he still has munition. If yes, a shot is fired and it is checked,
    # if an enemy is hit
    def player_shoot(self, x, y):
        if self.munition_counter > 0:
            self.munition_counter -= 1
            self.play_sound("shot")
            self.bullet_holes.append([x, y])

            # check for each enemy, if the x and y are within an enemy
            for enemy in self.enemies:
                dist = math.hypot(x - enemy.rect.centerx, y - enemy.rect.centery)
                radius = Constants.ENEMY_SIZE/2
                if dist < radius:
                    self.shot_enemy = True
                    self.shooted_enemy = enemy
        else:
            self.play_sound("no_ammo")

    # Every time the user shoots, a hole is drawn on the screen.
    def draw_bullet_holes(self):
        for i in range(len(self.bullet_holes)):
            Constants.SCREEN.blit(Constants.BULLET_HOLE_IMAGE, (self.bullet_holes[i][0] - Constants.BULLET_HOLE_SIZE/2,
                                                                self.bullet_holes[i][1] - Constants.BULLET_HOLE_SIZE/2))
        if len(self.bullet_holes) > 30:  # If too many holes are on the screen, remove the oldest ones
            del self.bullet_holes[0]

    # checks if the player is overlapped by an enemy
    def check_enemy_behind(self):
        x = pygame.mouse.get_pos()[0]
        y = pygame.mouse.get_pos()[1]
        for enemy in self.enemies:
            check_for_overlapping = enemy.get_collision(enemy.rect.centerx, enemy.rect.centery,
                                                        self.player.rect.centerx, self.player.rect.centery)
            if check_for_overlapping:
                if "barricade_x" in self.barricade.keys():  # check if barricade is displayed
                    # if there is no collision between an enemy and the barricade that was drawn
                    if not self.check_barricade_collision(self.barricade["width"], self.barricade["height"],
                                                          self.barricade["barricade_x"],
                                                          self.barricade["barricade_y"]):
                        self.player_was_hit(enemy)
                else:  # if no barricade is displayed, decrease lives
                    self.player_was_hit(enemy)

    # decreases live of player and handles game over
    def player_was_hit(self, enemy):
        enemy.reset()
        self.play_sound("ouch")
        if self.lives > 1:
            self.lives -= 1
        else:
            self.stop_music()
            self.play_sound("game_over")
            self.game_over = True

    # checks if an enemy is overlapped by a barricade
    def check_barricade_collision(self, width, height, x, y):
        collision_with_barricade = False
        for enemy in self.enemies:
            radius = Constants.ENEMY_SIZE/2
            if enemy.rect.centerx + radius > x and enemy.rect.centerx + radius < x + width \
                    and enemy.rect.centery + radius < y + height and enemy.rect.centery > y:
                collision_with_barricade = True
        return collision_with_barricade

    # counts seconds and adds a new enemy after a certain time
    def check_level(self):
        position_arr_x = [0, Constants.WIDTH]
        position_arr_y = [0, Constants.HEIGHT]
        if self.level_seconds_counter > Constants.DURATION_BETWEEN_ENEMIES:  # adds an enemy every few ticks
            self.level_seconds_counter = 0

            for x in range(0, self.enemies_at_once+1):
                # adds an enemy that moves in from a random edge
                enemy = Enemy(1, position_arr_x[randint(0, 1)], position_arr_y[randint(0, 1)], 1, randint(1, 5))
                self.enemies.add(enemy)
        else:
            self.level_seconds_counter += 1

    # Using the collected coordinates, a line gets drawn on the screen when a user is in drawing mode
    def draw_user_drawing(self):
        if len(self.drawing_x_values) > 0:
            for i in range(len(self.drawing_x_values) - 1):
                pygame.draw.line(Constants.SCREEN, Constants.DRAWING_COLOR,
                                 [self.drawing_x_values[i], self.drawing_y_values[i]],
                                 [self.drawing_x_values[i+1], self.drawing_y_values[i+1]], 10)

    # draws an explosion animation, if the player has just shot an enemy
    def draw_explosion(self):
        if self.munition_counter > 0:
            if self.shot_enemy:
                # increase the number of the enemy sprite image with each tick and draw image
                if self.shoot_enemy_anim_iterator < self.shooted_enemy.get_explosion_duration():
                    self.shooted_enemy.explode(self.shoot_enemy_anim_iterator)
                    self.shoot_enemy_anim_iterator += 1
                else:
                    self.highscore += 100
                    self.enemies_incrementor += 100
                    if self.enemies_incrementor >= 1000:
                        self.enemies_at_once += 1
                        self.enemies_incrementor = 0
                    self.enemies.remove(self.shooted_enemy)
                    self.shot_enemy = False
                    self.shoot_enemy_anim_iterator = 0
                    self.shooted_enemy = None

    # necessary for closing the window in pygame
    def init_pygame_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()

            # Only for testing with the Mouse instead of the Wiimote
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    exit()
                elif event.key == pygame.K_RETURN:
                    self.munition_counter = Constants.MUNITION_COUNT
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self.player_shoot(pygame.mouse.get_pos()[0], pygame.mouse.get_pos()[1])

    # Pass the accelerometer values of the pointing wiimote to the ActivityRecogizer class and wait for a prediction
    def recognize_activity(self):
        accelerometer = self.wm_pointer.accelerometer
        predicted_activity = self.activity_recognizer.predict_activity(accelerometer[0], accelerometer[1],
                                                                       accelerometer[2])
        if predicted_activity == "reload":
            self.reload()

    # handles the reloading of the munition
    def reload(self):
        if self.munition_counter == 0:
            self.play_sound("reload")
            self.munition_counter = Constants.MUNITION_COUNT


"""
This class is responsible for reading in highscore data from a csv file and writing new entries to that file
"""


class Highscore:

    def __init__(self):
        self.highscore_entries = []
        self.read_data_from_csv()

    # Read in the top highscore entries from the corresponding csv file
    def read_data_from_csv(self):
        csv_files = glob.glob("*.csv")  # get all csv files from the directory
        for file in csv_files:
            if file == "highscore.csv":
                for line in open(file, "r").readlines():
                    name, points = line.split(',')
                    self.highscore_entries.append([name, int(points)])

    def get_highscore(self):
        return self.highscore_entries

    def update_highscore(self, name, points):
        self.highscore_entries.append([name, points])
        # Sort a list of lists:
        # https://stackoverflow.com/questions/4174941/how-to-sort-a-list-of-lists-by-a-specific-index-of-the-inner-list
        self.highscore_entries.sort(key=lambda x: x[1])
        # Reverse a list: https://stackoverflow.com/questions/3940128/how-can-i-reverse-a-list-in-python
        self. highscore_entries = self.highscore_entries[::-1]
        # Trim list to the top 10 entries
        if len(self.highscore_entries) > 10:
            self.highscore_entries = self.highscore_entries[:10]

        self.update_csv_file()

    # Update the csv file by  overwriting the file
    def update_csv_file(self):
        file = open("highscore.csv", "w")
        writer = csv.writer(file)
        for i in range(len(self.highscore_entries)):
            writer.writerow([self.highscore_entries[i][0], self.highscore_entries[i][1]])
        file.close()


"""
This class handles an Enemy GameObject.
Implemented like here: # from http://kidscancode.org/blog/2016/08/pygame_1-2_working-with-sprites/
"""


class Enemy(pygame.sprite.Sprite):
    def __init__(self, id, x, y, speed, randint):
        pygame.sprite.Sprite.__init__(self)
        self.id = id
        self.speed = speed

        # sets the image of the enemy objects (randomly select one of five)
        self.circle_img = pygame.image.load(path.join(Constants.IMG_DIR, str(randint)+".png")).convert()
        self.image = self.circle_img
        # scales down image
        self.image = pygame.transform.scale(self.circle_img, (Constants.ENEMY_SIZE, Constants.ENEMY_SIZE))
        self.image.set_colorkey((250, 250, 250))  # avoids a black background

        # specifies position of enemy
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
        self.enemy_iterator = 0

        # init enemy values
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

    # sets explosion image to image in list index defined by iterator that is passed in update method
    def explode(self, iterator):
        self.speed = 0  # hinder enemy to move any further if he was shooted
        self.image = pygame.transform.scale(self.explosion_sprite[iterator], (90, 90))
        self.image.set_colorkey((0, 0, 0))

    # gets the length of the image list that represents the explosion animation
    def get_explosion_duration(self):
        return len(self.explosion_sprite)

    # The enemies can track the player. Code example taken from
    # from https://stackoverflow.com/questions/20044791/how-to-make-an-enemy-follow-the-player-in-pygame
    def move_towards_player(self, Player):
        self.image.set_colorkey((0, 0, 0))  # removes black background from transparent image
        speed = self.speed
        px = Player.rect.centerx
        py = Player.rect.centery
        # Movement along x direction
        if self.rect.centerx > px:
            self.rect.centerx -= speed
            self.enemy_delay = Constants.ENEMY_DELAY
        elif self.rect.centerx < px:
            self.rect.centerx += speed
            self.enemy_delay = Constants.ENEMY_DELAY
        # Movement along y direction
        if self.rect.centery < py:
            self.rect.centery += speed
            self.enemy_delay = Constants.ENEMY_DELAY
        elif self.rect.centery > py:
            self.rect.centery -= speed
            self.enemy_delay = Constants.ENEMY_DELAY

    # returns whether an enemy is overlapped with the player
    def get_collision(self, enemyx, enemyy, x, y):
        collision = False
        radius = Constants.ENEMY_SIZE/20
        dist = math.hypot(x - enemyx, y - enemyy)
        if dist < radius:
            if self.enemy_delay <= 0:
                self.lose_live = True
            else:
                self.enemy_delay -= 1

                collision = True
        return collision

    # resets enemy to start position
    def reset(self):
        self.rect.x = 10
        self.rect.y = 10
        self.lose_live = False
        self.enemy_delay = Constants.ENEMY_DELAY


"""
This class is responsible for the player game obect
Implemented like here: from http://kidscancode.org/blog/2016/08/pygame_shmup_part_1/
"""


class Player(pygame.sprite.Sprite):

    def __init__(self):
        pygame.sprite.Sprite.__init__(self)
        self.image = pygame.Surface((100, 100))
        self.image.fill((0, 255, 0))
        self.rect = self.image.get_rect()
        self.rect.centerx = Constants.WIDTH / 2
        self.rect.bottom = Constants.HEIGHT - 200
        self.speedx = 0
        self.centerx = Constants.WIDTH / 2
        self.centery = Constants.HEIGHT / 2

    # Update the player position
    def set_player_coordinates(self, x, y):
        self.centerx = x
        self.centery = y

    def get_player_coordinates(self):
        return self.centerx, self.centery

    def update(self):
        self.speedx = 0
        self.speedy = 0
        self.rect.x = self.centerx
        self.rect.y = self.centery

        # prevents the player to get outside of the screen
        if self.rect.right > Constants.WIDTH:
            self.rect.right = Constants.WIDTH
        if self.rect.left < 0:
            self.rect.left = 0


"""
This class is responsible for the Crosshair used for aiming
"""


class Crosshairs(pygame.sprite.Sprite):
    def __init__(self):
        pygame.sprite.Sprite.__init__(self)
        self.image = Constants.CROSSHAIR_IMAGE  # set crosshair image
        self.image = pygame.transform.scale(self.image, (Constants.CROSSHAIR_SIZE, Constants.CROSSHAIR_SIZE))
        self.image.set_colorkey((0, 0, 0))
        self.rect = self.image.get_rect()

        pygame.mouse.set_visible(0)  # Make Mouse Cursor invisible

    # updates crosshair based on current mouse position with every tick
    def update(self):
        mousex, mousey = pygame.mouse.get_pos()
        self.rect.centerx = mousex
        self.rect.centery = mousey


"""
This class is responsible for the activity recognition. It is used for detecting the reload gesture
(poining the wiimote upwards -> shake the wiimote -> point the wiimote forwards)
The code for this class has been taken from the solution for Assignment08 by Andrea Fischer and Vitus Maierhöfer
"""


class ActivityRecognizer:

    def __init__(self):
        self.category_list = []
        self.ready_for_prediction = False
        self.c = svm.SVC()
        self.prediction_values = [[], [], []]
        self.minlen = 1000  # Just a large value to begin with, far larger than the values we can expect
        self.read_data_from_csv()

    def get_categories(self):
        csv_files = glob.glob(path.join("activity_templates", "*.csv"))  # get all csv files from the folder
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
        if len(categories) == 0:  # No Categories exist. Training not possible
            return
        if len(categories) < 2:  # Not enough categories created to train
            return

        for category in categories:
            activities[category] = []

        csv_files = glob.glob(path.join("activity_templates", "*.csv"))
        if len(csv_files) == 0:  # If no CSV Files to train with exist
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

    # Cut date to the right length
    def cut_off_data(self, activities):
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

    # Train the machine learning classifier
    def train(self, activities):
        categories = []
        training_data = []

        for activity_name, value in activities.items():
            for i in range(len(value)):
                categories.append(activity_name)
                training_data.append(value[i])

        self.c.fit(training_data, categories)
        self.ready_for_prediction = True

    # Recognize the acitivity using the values from the wiimote accelerometer
    def predict_activity(self, x, y, z):

        if self.ready_for_prediction:
            if len(self.prediction_values[0]) < self.minlen:  # Buffer enough values for prediction
                self.prediction_values[0].append(x)
                self.prediction_values[1].append(y)
                self.prediction_values[2].append(z)
                return ""
            else:
                avg = []
                for i in range(len(self.prediction_values[0])):
                    avg.append((self.prediction_values[0][i] + self.prediction_values[1][i] +
                                self.prediction_values[2][i]) / 3)

                self.prediction_values = [[], [], []]

                # This line is taken from the "Wiimote - FFT - SVM" notebook from Grips
                freq = [np.abs(fft(avg) / len(avg))[1:len(avg) // 2]]
                return str(self.c.predict(freq)[0])


"""
This class implements the $1 gesture recognizer from the paper: Wobbrock, J.O., Wilson, A.D. and Li, Y. (2007).
Gestures without libraries, toolkits or training: A $1 recognizer for user interface prototypes.
The code has been taken from the solution of Assignment09 from Andrea Fischer and Miriam Schlindwein
"""


class GestureRecognizer:

    def __init__(self):
        self.gestures = []
        self.names = []
        self.N = 64
        self.size = 100
        self.origin = 100, 100
        self.ratio = 1/2 * (-1 + np.sqrt(5))
        self.load_templates()

    # get all templates that are stored as data values within csv files
    def load_templates(self):
        csv_files = glob.glob(path.join("drawing_templates", "*.csv"))  # get all csv files from the directory

        for file in csv_files:
            # split file at ".", so that only the name without ".csv" is returned
            filename = file.split(".")[0]
            self.names.append(filename)
            template = []

            with open(file) as csvfile:
                readcsv = csv.reader(csvfile, delimiter=',')
                for row in readcsv:
                    # get content of csv and store it in template list
                    template.append([float(row[0]), float(row[1])])
            self.gestures.append(template)

    # Try to recognize the drawing using the passed coordinates
    def recognize_drawing(self, drawing_x_coordinates, drawing_y_coordinates):
        if len(drawing_x_coordinates) < 4:  # Skip recognition if not enough points are drawn (so no error shows)
            return

        points = []

        for i in range(len(drawing_x_coordinates)):
            points.append([drawing_x_coordinates[i], drawing_y_coordinates[i]])

        resampled_points = self.resample(points)
        rotated_points = self.rotate(resampled_points)
        scaled_points = self.scale(rotated_points)
        points_for_recognition = self.translate(scaled_points)
        recgonize = self.recognize(points_for_recognition)

        return recgonize

    def resample(self, gesture):
        """the input gestures are sampled to the length n and the list newPoints is returned"""
        newPoints = [gesture[0]]
        distance = 0.0
        path = self.pathLength(gesture)
        pathLen = path / (self.N - 1)
        i = 1
        while i < len(gesture):
            d = self.Distance(gesture[i-1], gesture[i])
            if distance + d >= pathLen:
                x = gesture[i-1][0] + ((pathLen - distance)/d) * (gesture[i][0] - gesture[i-1][0])
                y = gesture[i-1][1] + ((pathLen - distance)/d) * (gesture[i][1] - gesture[i-1][1])
                q = (x, y)
                newPoints.append(q)
                gesture.insert(i, q)
                distance = 0.0
            else:
                distance += d
            i += 1
        if len(newPoints) == self.N - 1:
            newPoints.append(gesture[len(gesture)-1])
        return newPoints

    def Distance(self, p1, p2):
        """the distance between two points is calculated and returned"""
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        return math.sqrt(dx*dx + dy*dy)

    def centroid(self, gesture):
        """the centroid of the gesture is calculated and returned"""
        x = y = 0
        for i in range(len(gesture)):
            x = x + gesture[i][0]
            y = y + gesture[i][1]

        x = x/len(gesture)
        y = y/len(gesture)
        return x, y

    def pathLength(self, gesture):
        """the length of the gesture including all points is calculated and returned"""
        distance = 0.0
        for i in range(1, len(gesture)):
            d = self.Distance(gesture[i - 1], gesture[i])
            distance += d

        return distance

    def rotate(self, gesture):
        """the gesture is rotated and returned"""
        centroid = self.centroid(gesture)
        radians = np.arctan2(centroid[1]-gesture[0][1], centroid[0]-gesture[0][0])
        newPoints = self.rotateBy(gesture, radians)
        return newPoints

    def rotateBy(self, gesture, radians):
        """the gesture is rotated depending on the given angle"""
        centroid = self.centroid(gesture)
        cos = np.cos(-radians)
        sin = np.sin(-radians)
        newPoints = []
        for i in range(len(gesture)):
            x = (gesture[i][0] - centroid[0]) * cos - (gesture[i][1] - centroid[1]) * sin + centroid[0]
            y = (gesture[i][0] - centroid[0]) * sin + (gesture[i][1] - centroid[1]) * cos + centroid[1]
            newPoints.append([float(x), float(y)])
        return newPoints

    def scale(self, gesture):
        """the gesture is scaled to a defined size and the calculated newPoints are returned"""
        self.boundingBox = self.getBoundingBox(gesture)
        newPoints = []
        for i in range(len(gesture)):

            x = gesture[i][0] * (self.size / (self.boundingBox[1][0] - self.boundingBox[0][0]))
            y = gesture[i][1] * (self.size / (self.boundingBox[1][1] - self.boundingBox[0][1]))

            newPoints.append([float(x), float(y)])

        return newPoints

    def getBoundingBox(self, gesture):
        """defines the minimum and maximum points of the gesture and returns these"""
        minX, minY = np.min(gesture, 0)
        maxX, maxY = np.max(gesture, 0)

        return (minX, minY), (maxX, maxY)

    def translate(self, gesture):
        """the gesture is translated depending on the given origin point, the calculated new points are returned"""
        newPoints = []
        c = np.mean(gesture, 0)
        for i in range(len(gesture)):
            x = gesture[i][0] + self.origin[0] - c[0]
            y = gesture[i][1] + self.origin[1] - c[1]
            newPoints.append([float(x), float(y)])

        return newPoints

    def recognize(self, points):
        """calculates the distance between points and templates and returns the number of template
        if there is no recognition False is returned"""
        b = np.inf
        angle = 45
        a = 2
        for i in range(len(self.gestures)):
            template = self.gestures[i]
            d = self.distanceAtBestAngle(points, template, - angle, angle, a)
            if d < b:
                b = d
        if b < 15:
            return True
        else:
            return False

    def distanceAtBestAngle(self, points, T, minAngle, angle, a):
        """the minimum distance in dependence on the angle is calculated"""
        x1 = self.ratio * minAngle + (1-self.ratio) * angle
        f1 = self.distanceAtAngle(points, T, x1)
        x2 = (1-self.ratio) * minAngle + self.ratio * angle
        f2 = self.distanceAtAngle(points, T, x2)

        while np.abs(angle - minAngle) > a:
            if f1 < f2:
                angle = x2
                x2 = x1
                f2 = f1
                x1 = self.ratio*minAngle + (1 - self.ratio) * angle
                f1 = self.distanceAtAngle(points, T, x1)
            else:
                minAngle = x1
                x1 = x2
                f1 = f2
                x2 = (1-self.ratio)*minAngle + self.ratio*angle
                f2 = self.distanceAtAngle(points, T, x2)

        return min(f1, f2)

    def distanceAtAngle(self, points, T, x1):
        """the distance between points and template is calculated"""
        newPoints = self.rotateBy(points, x1)
        d = self.pathDistance(newPoints, T)
        return d

    def pathDistance(self, A, B):
        """the path Distance between gesture A and a gesture from the """
        d = 0
        for i in range(len(A)):
            d += self.Distance(A[i], B[i])
        return d/len(A)


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

        # The following 16 lines of code responsible for sorting are taken from the file "transform.py"
        # of Andrea Fischers and Miriam Schlindweins solution of of Assignment09
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

        # Step 1
        source_points_123 = np.matrix([[A[0], B[0], C[0]], [A[1], B[1], C[1]], [1, 1, 1]])
        source_point_4 = [[D[0]], [D[1]], [1]]

        scale_to_source = np.linalg.solve(source_points_123, source_point_4)
        l, m, t = [float(x) for x in scale_to_source]

        # Step 2
        unit_to_source = np.matrix([[l * A[0], m * B[0], t * C[0]], [l * A[1], m * B[1], t * C[1]], [l, m, t]])

        # Step 3
        A2 = 0, Constants.HEIGHT
        B2 = 0, 0
        C2 = Constants.WIDTH, 0
        D2 = Constants.WIDTH, Constants.HEIGHT

        dest_points_123 = np.matrix([[A2[0], B2[0], C2[0]], [A2[1], B2[1], C2[1]], [1, 1, 1]])

        dest_point_4 = np.matrix([[D2[0]], [D2[1]], [1]])

        scale_to_dest = np.linalg.solve(dest_points_123, dest_point_4)
        l, m, t = [float(x) for x in scale_to_dest]

        unit_to_dest = np.matrix([[l * A2[0], m * B2[0], t * C2[0]], [l * A2[1], m * B2[1], t * C2[1]],  [l, m, t]])

        # Step 4: Invert  A  to obtain  A−1
        try:
            source_to_unit = np.linalg.inv(unit_to_source)
        except np.linalg.linalg.LinAlgError:
            return 0, 0

        # Step 5: Compute the combined matrix
        source_to_dest = unit_to_dest @ source_to_unit

        # Step 6: To map a location  (x,y)  from the source image to its corresponding location in the destination
        # image, compute the product
        x, y, z = [float(w) for w in (source_to_dest @ np.matrix([[512], [384], [1]]))]

        # step 7: dehomogenization
        x = int(x / z)
        y = int(y / z)

        return x, y


"""
This class gets the coordinates of the two LEDs of the head tracking device as input and calculates the position of
the player on the screen.
"""


class Tracking:

    def process_ir_data_two_leds(self, left, right):

        # Since we want direct movement (e.g move head up -> move player on screen up), the coordinate points need
        # to be inverted. Otherwise, movements will be in the wrong direction
        inverted_left = (Constants.WIIMOTE_IR_CAM_WIDTH - left[0], Constants.WIIMOTE_IR_CAM_HEIGHT - left[1])
        inverted_right = (Constants.WIIMOTE_IR_CAM_WIDTH - right[0], Constants.WIIMOTE_IR_CAM_HEIGHT - right[1])

        # After getting the coordinates of the two LEDs, we need to calculate the point in the middle of the two
        # coordinates. This is the center of our head.
        center = ((inverted_left[0] + inverted_right[0]) / 2, (inverted_left[1] + inverted_right[1]) / 2)

        # The coordinates of the head center are for the resolution of the Wiimote IR Cam (1024x768). To position
        # the player correctly on the screen, new coordinates need to be calculated, suited for
        # the resolution of the screen.
        x_on_screen = int((center[0] / Constants.WIIMOTE_IR_CAM_WIDTH) * Constants.WIDTH)
        y_on_screen = int((center[1] / Constants.WIIMOTE_IR_CAM_HEIGHT) * Constants.HEIGHT)

        if Constants.INVERT_HEAD_TRACKING_LEFT_RIGHT:
            x_on_screen = Constants.WIDTH - x_on_screen  # Invert x

        return x_on_screen, y_on_screen


def main():
    wiimote_game = WiimoteGame()
    sys.exit()


if __name__ == '__main__':
    main()
