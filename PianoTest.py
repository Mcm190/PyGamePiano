import pygame
import mido
import sys
import os
import math
import array
import random
import colorsys

# config
WIDTH, HEIGHT = 1280, 800
FPS = 60
PIANO_HEIGHT = 140
HIT_LINE_Y = HEIGHT - PIANO_HEIGHT
PIXELS_PER_SECOND = 200
SCROLL_SPEED_MULT = 1.0
BG_IMAGE_PATH = "assets/background.jpg"

# colours
COLOR_BG = (10, 12, 20)
COLOR_GRID = (30, 30, 50)
COLOR_KEY_WHITE = (230, 230, 240)
COLOR_KEY_BLACK = (20, 20, 25)

# audio stuff
pygame.mixer.pre_init(44100, 32, 2, 2048)
pygame.init()
pygame.mixer.set_num_channels(512) 

class PianoSynth:
    def __init__(self):
        self.sounds = {}
        folder = "assets/sounds/final"
        if os.path.exists(folder):
            print("Loading WAV samples...")
            for f in os.listdir(folder):
                if f.endswith(".wav"):
                    try:
                        midi = int(os.path.splitext(f)[0])
                        self.sounds[midi] = pygame.mixer.Sound(os.path.join(folder, f))
                    except: pass
        else:
            print("No samples found. Using Synth.")
        
    def play(self, midi, velocity):
        vol = velocity * 0.5 
        if midi in self.sounds:
            s = self.sounds[midi]
            s.set_volume(vol)
            s.play()
        else:
            self._play_generated(midi, vol)

    def _play_generated(self, midi, vol):
        freq = 440.0 * (2.0 ** ((midi - 69) / 12.0))
        sample_rate = 44100
        duration = 2.5 
        n_samples = int(sample_rate * duration)
        
        buf = array.array('f') 
        for i in range(n_samples):
            t = i / sample_rate
            val = math.sin(2 * math.pi * freq * t)
            val += 0.5 * math.sin(4 * math.pi * freq * t)
            decay = math.exp(-4 * t) 
            sample = val * decay * vol
            buf.append(sample)
            
        stereo_buf = array.array('f')
        for s in buf:
            stereo_buf.append(s)
            stereo_buf.append(s)
            
        s = pygame.mixer.Sound(stereo_buf)
        s.play()

audio_engine = PianoSynth()

# visuals

class Particle:
    def __init__(self, x, y, color, surf):
        self.x = x
        self.y = y
        self.surf = surf 
        self.vx = random.uniform(-2, 2)
        self.vy = random.uniform(-5, -2)
        self.life = 1.0
        self.decay = random.uniform(0.03, 0.06)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vy += 0.15
        self.life -= self.decay

    def draw(self, surface):
        if self.life > 0:
            self.surf.set_alpha(int(self.life * 255))
            surface.blit(self.surf, (self.x, self.y), special_flags=pygame.BLEND_ADD)

class VisualFxManager:
    def __init__(self):
        self.particles = []
        self.glow_surfs = {} 
    
    def get_glow_surf(self, color):
        key = tuple(color)
        if key not in self.glow_surfs:
            size = 8
            s = pygame.Surface((size*2, size*2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*color, 255), (size, size), size)
            self.glow_surfs[key] = s
        return self.glow_surfs[key]

    def spawn_explosion(self, x, y, width, color):
        surf = self.get_glow_surf(color)
        for _ in range(10):
            px = x + random.random() * width
            self.particles.append(Particle(px, y, color, surf))

    def update_and_draw(self, surface):
        self.particles = [p for p in self.particles if p.life > 0]
        for p in self.particles:
            p.update()
            p.draw(surface)

fx_manager = VisualFxManager()

# game classes

class Key:
    def __init__(self, midi, x, width, height, is_black):
        self.midi = midi
        self.rect = pygame.Rect(x, HIT_LINE_Y, width, height)
        self.is_black = is_black
        self.is_pressed = False
        self.color_active = (0,0,0)
        self.brightness = 0.0
        self.fade_speed = 0.0
        
        self.base_surf = pygame.Surface((width, height))
        if is_black:
            self.base_surf.fill(COLOR_KEY_BLACK)
            pygame.draw.rect(self.base_surf, (50,50,60), (2, 0, width-4, height-5), border_radius=3)
        else:
            self.base_surf.fill(COLOR_KEY_WHITE)
            s = pygame.Surface((width, 20), pygame.SRCALPHA)
            for i in range(20):
                alpha = 100 - (i * 5)
                pygame.draw.line(s, (0,0,0,alpha), (0,i), (width,i))
            self.base_surf.blit(s, (0,0))

    def press(self, velocity, duration_seconds):
        self.is_pressed = True
        hue = (self.midi % 12) / 12.0
        rgb = colorsys.hsv_to_rgb(hue, 0.8, 1.0)
        self.color_active = (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))

        audio_engine.play(self.midi, velocity)
        fx_manager.spawn_explosion(self.rect.x, self.rect.y, self.rect.width, self.color_active)
        
        self.brightness = 1.0
        if duration_seconds > 0:
            total_frames = duration_seconds * FPS
            self.fade_speed = 0.8 / max(1, total_frames)
        else:
            self.fade_speed = 0.05

    def release(self):
        self.is_pressed = False
        self.brightness = 0.0

    def update(self):
        if self.is_pressed:
            self.brightness -= self.fade_speed
            if self.brightness < 0.2: self.brightness = 0.2

    def draw(self, surface):
        surface.blit(self.base_surf, self.rect.topleft)
        if self.is_pressed or self.brightness > 0.01:
            alpha = int(self.brightness * 255)
            if alpha > 0:
                overlay = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
                overlay.fill((*self.color_active, int(alpha * 0.7)))
                surface.blit(overlay, self.rect.topleft, special_flags=pygame.BLEND_ADD)
                pygame.draw.rect(surface, self.color_active, self.rect, 2, border_radius=3)

class FallingNote:
    def __init__(self, midi, start_sec, end_sec, velocity, key_rect):
        self.midi = midi
        self.start_time = start_sec
        self.end_time = end_sec
        self.duration = end_sec - start_sec
        self.velocity = velocity
        self.key_x = key_rect.x + 1
        self.width = key_rect.width - 2
        self.hit = False
        self.playing = False
        
        hue = (midi % 12) / 12.0
        rgb = colorsys.hsv_to_rgb(hue, 0.7, 1.0)
        self.color_main = (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
        rgb_light = colorsys.hsv_to_rgb(hue, 0.3, 1.0) 
        self.color_center = (int(rgb_light[0]*255), int(rgb_light[1]*255), int(rgb_light[2]*255))

    def draw(self, surface, current_time):
        time_until_hit = self.start_time - current_time
        y_head = HIT_LINE_Y - (time_until_hit * PIXELS_PER_SECOND * SCROLL_SPEED_MULT)
        length = self.duration * PIXELS_PER_SECOND * SCROLL_SPEED_MULT
        y_tail = y_head - length
        
        if y_head > -50 and y_tail < HEIGHT:
            r = pygame.Rect(self.key_x, y_tail, self.width, length)
            pygame.draw.rect(surface, self.color_main, r, border_radius=4)
            if self.width > 6:
                center_r = r.inflate(-6, -4)
                pygame.draw.rect(surface, self.color_center, center_r, border_radius=2)
            pygame.draw.line(surface, (255,255,255), (r.left+2, r.bottom-2), (r.right-2, r.bottom-2), 2)

# data loading/structures

keys = []
key_map = {}
notes_list = []
tempo_map = [] 

def setup_keys():
    cursor_x = 0
    wk_width = WIDTH / 52
    bk_width = wk_width * 0.65
    
    for i in range(21, 109):
        if not ((i % 12) in [1, 3, 6, 8, 10]):
            k = Key(i, cursor_x, wk_width, PIANO_HEIGHT, False)
            keys.append(k); key_map[i] = k
            cursor_x += wk_width
    for i in range(21, 109):
        if (i % 12) in [1, 3, 6, 8, 10]:
            prev = key_map.get(i-1)
            if prev:
                k = Key(i, prev.rect.right - (bk_width/2), bk_width, PIANO_HEIGHT*0.65, True)
                keys.append(k); key_map[i] = k

def parse_midi(filename):
    print(f"Parsing {filename}...")
    mid = mido.MidiFile(filename)
    merged_msgs = mido.merge_tracks(mid.tracks)
    
    current_time_sec = 0.0
    current_tempo = 500000
    ticks_per_beat = mid.ticks_per_beat
    active_notes = {}
    
    for msg in merged_msgs:
        time_delta = mido.tick2second(msg.time, ticks_per_beat, current_tempo)
        current_time_sec += time_delta
        
        if msg.type == 'set_tempo':
            current_tempo = msg.tempo
            tempo_map.append((current_time_sec, mido.tempo2bpm(msg.tempo)))
        elif msg.type == 'note_on' and msg.velocity > 0:
            active_notes[msg.note] = (current_time_sec, msg.velocity)
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            if msg.note in active_notes:
                start_t, start_v = active_notes.pop(msg.note)
                if msg.note in key_map:
                    k = key_map[msg.note]
                    note = FallingNote(msg.note, start_t, current_time_sec, start_v/127.0, k.rect)
                    notes_list.append(note)
    
    notes_list.sort(key=lambda x: x.start_time)
    if not tempo_map: tempo_map.append((0, 120))


setup_keys()
if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
    parse_midi(sys.argv[1])
else:
    print("No MIDI, Generating demo notes...")
    dummy_start = 2.0
    for i in range(50):
        n = FallingNote(60 + (i%12), dummy_start, dummy_start+0.5, 0.8, key_map[60+(i%12)].rect)
        notes_list.append(n)
        dummy_start += 0.2

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption(".midi piano player")

# background stuff
bg_surface = pygame.Surface((WIDTH, HEIGHT))

if os.path.exists(BG_IMAGE_PATH):
    try:
        print(f"Loading background: {BG_IMAGE_PATH}")
        img = pygame.image.load(BG_IMAGE_PATH).convert()
        img = pygame.transform.smoothscale(img, (WIDTH, HEIGHT))
        bg_surface.blit(img, (0,0))
        
        # dark overlay
        dark_overlay = pygame.Surface((WIDTH, HEIGHT))
        dark_overlay.fill((10, 10, 15))
        dark_overlay.set_alpha(200)
        bg_surface.blit(dark_overlay, (0,0))
    except Exception as e:
        print(f"Error loading background: {e}")

else:
    # fallback to procedural gradient
    print("Background image not found. Using Gradient.")
    for y in range(HEIGHT):
        r = max(0, COLOR_BG[0] - y//20)
        g = max(0, COLOR_BG[1] - y//20)
        b = max(0, COLOR_BG[2] + y//15)
        pygame.draw.line(bg_surface, (r,g,b), (0, y), (WIDTH, y))

# draw grid lines
for x in range(0, WIDTH, 40):
    pygame.draw.line(bg_surface, (20, 20, 40), (x, 0), (x, HEIGHT), 1)


clock = pygame.time.Clock()
running = True
playback_time = 0.0
current_bpm = 120.0

while running:
    dt = (clock.get_time() / 1000.0) * SCROLL_SPEED_MULT
    if dt > 0.1: dt = 0.1 
    
    playback_time += dt

    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP: SCROLL_SPEED_MULT += 0.1
            if event.key == pygame.K_DOWN: SCROLL_SPEED_MULT = max(0.1, SCROLL_SPEED_MULT - 0.1)
            if event.key == pygame.K_LEFT: playback_time -= 2.0
            if event.key == pygame.K_RIGHT: playback_time += 2.0

    for t_sec, t_bpm in reversed(tempo_map):
        if playback_time >= t_sec: current_bpm = t_bpm; break

    screen.blit(bg_surface, (0,0))

    for note in notes_list:
        if note.start_time > playback_time + 8: break
        if note.end_time < playback_time - 1: continue
        
        note.draw(screen, playback_time)
        
        if not note.hit and playback_time >= note.start_time:
            if note.midi in key_map: 
                key_map[note.midi].press(note.velocity, note.duration)
            note.hit = True
            
        if note.hit and not note.playing and playback_time >= note.end_time:
            if note.midi in key_map: 
                key_map[note.midi].release()
            note.playing = True

    fx_manager.update_and_draw(screen)

    pygame.draw.rect(screen, (0,0,0), (0, HIT_LINE_Y-5, WIDTH, 10))
    for k in keys:
        if not k.is_black: k.update(); k.draw(screen)
    for k in keys:
        if k.is_black: k.update(); k.draw(screen)

    pygame.draw.line(screen, (50, 200, 255), (0, HIT_LINE_Y), (WIDTH, HIT_LINE_Y), 1)
    
    s = pygame.Surface((WIDTH, PIANO_HEIGHT), pygame.SRCALPHA)
    pygame.draw.rect(s, (0,0,0, 50), s.get_rect())
    screen.blit(s, (0, HIT_LINE_Y))

    # bpm display
    font = pygame.font.SysFont("Consolas", 20)
    ui_str = f"BPM: {int(current_bpm)}"
    
    # text shadow
    screen.blit(font.render(ui_str, True, (0,0,0)), (12, 12))
    # text colour
    screen.blit(font.render(ui_str, True, (100, 255, 200)), (10, 10))

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()