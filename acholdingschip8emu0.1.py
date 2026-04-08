import tkinter as tk
from tkinter import filedialog, messagebox
import random
import os
import time

# Standard CHIP-8 Fontset
FONTSET = [
    0xF0, 0x90, 0x90, 0x90, 0xF0, 0x20, 0x60, 0x20, 0x20, 0x70,
    0xF0, 0x10, 0xF0, 0x80, 0xF0, 0xF0, 0x10, 0xF0, 0x10, 0xF0,
    0x90, 0x90, 0xF0, 0x10, 0x10, 0xF0, 0x80, 0xF0, 0x10, 0xF0,
    0xF0, 0x80, 0xF0, 0x90, 0xF0, 0xF0, 0x10, 0x20, 0x40, 0x40,
    0xF0, 0x90, 0xF0, 0x90, 0xF0, 0xF0, 0x90, 0xF0, 0x10, 0xF0,
    0xF0, 0x90, 0xF0, 0x90, 0x90, 0xE0, 0x90, 0xE0, 0x90, 0xE0,
    0xF0, 0x80, 0x80, 0x80, 0xF0, 0xE0, 0x90, 0x90, 0x90, 0xE0,
    0xF0, 0x80, 0xF0, 0x80, 0xF0, 0xF0, 0x80, 0xF0, 0x80, 0x80
]

KEY_MAP = {
    '1': 0x1, '2': 0x2, '3': 0x3, '4': 0xC,
    'q': 0x4, 'w': 0x5, 'e': 0x6, 'r': 0xD,
    'a': 0x7, 's': 0x8, 'd': 0x9, 'f': 0xE,
    'z': 0xA, 'x': 0x0, 'c': 0xB, 'v': 0xF
}

class Chip8Core:
    def __init__(self, bell_callback):
        self.bell_callback = bell_callback 
        self.reset()

    def reset(self):
        self.memory = bytearray(4096)
        self.v = bytearray(16)
        self.i = 0
        self.pc = 0x200
        self.stack = []
        self.delay_timer = 0
        self.sound_timer = 0
        self.gfx = bytearray(64 * 32)
        self.draw_flag = True
        self.key = bytearray(16)
        self.wait_key_reg = -1
        for i, byte in enumerate(FONTSET):
            self.memory[0x050 + i] = byte

    def load_rom(self, rom_data):
        self.reset()
        for i, byte in enumerate(rom_data):
            if 0x200 + i < 4096: self.memory[0x200 + i] = byte

    def cycle(self):
        if self.wait_key_reg != -1:
            for i in range(16):
                if self.key[i]:
                    self.v[self.wait_key_reg] = i
                    self.wait_key_reg = -1
                    return
            return

        opcode = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        self.pc += 2

        nib = (opcode & 0xF000) >> 12
        x = (opcode & 0x0F00) >> 8
        y = (opcode & 0x00F0) >> 4
        n = opcode & 0x000F
        nn = opcode & 0x00FF
        nnn = opcode & 0x0FFF

        if opcode == 0x00E0: 
            self.gfx = bytearray(64 * 32)
            self.draw_flag = True
        elif opcode == 0x00EE: 
            if self.stack: self.pc = self.stack.pop()
        elif nib == 0x1: self.pc = nnn
        elif nib == 0x2: self.stack.append(self.pc); self.pc = nnn
        elif nib == 0x3: 
            if self.v[x] == nn: self.pc += 2
        elif nib == 0x4: 
            if self.v[x] != nn: self.pc += 2
        elif nib == 0x5: 
            if self.v[x] == self.v[y]: self.pc += 2
        elif nib == 0x6: self.v[x] = nn
        elif nib == 0x7: self.v[x] = (self.v[x] + nn) & 0xFF
        elif nib == 0x8:
            if n == 0x0: self.v[x] = self.v[y]
            elif n == 0x1: self.v[x] |= self.v[y]
            elif n == 0x2: self.v[x] &= self.v[y]
            elif n == 0x3: self.v[x] ^= self.v[y]
            elif n == 0x4:
                res = self.v[x] + self.v[y]
                self.v[0xF] = 1 if res > 255 else 0
                self.v[x] = res & 0xFF
            elif n == 0x5:
                self.v[0xF] = 1 if self.v[x] >= self.v[y] else 0
                self.v[x] = (self.v[x] - self.v[y]) & 0xFF
            elif n == 0x6:
                self.v[0xF] = self.v[x] & 0x1
                self.v[x] >>= 1
            elif n == 0x7:
                self.v[0xF] = 1 if self.v[y] >= self.v[x] else 0
                self.v[x] = (self.v[y] - self.v[x]) & 0xFF
            elif n == 0xE:
                self.v[0xF] = (self.v[x] & 0x80) >> 7
                self.v[x] = (self.v[x] << 1) & 0xFF
        elif nib == 0x9: 
            if self.v[x] != self.v[y]: self.pc += 2
        elif nib == 0xA: self.i = nnn
        elif nib == 0xB: self.pc = nnn + self.v[0]
        elif nib == 0xC: self.v[x] = random.randint(0, 255) & nn
        elif nib == 0xD:
            vx, vy = self.v[x] % 64, self.v[y] % 32
            self.v[0xF] = 0
            for row in range(n):
                if vy + row >= 32: break
                sprite_byte = self.memory[self.i + row]
                for col in range(8):
                    if vx + col >= 64: break
                    if sprite_byte & (0x80 >> col):
                        idx = (vx + col) + ((vy + row) * 64)
                        if self.gfx[idx] == 1: self.v[0xF] = 1
                        self.gfx[idx] ^= 1
            self.draw_flag = True
        elif nib == 0xE:
            if nn == 0x9E: 
                if self.key[self.v[x]]: self.pc += 2
            elif nn == 0xA1: 
                if not self.key[self.v[x]]: self.pc += 2
        elif nib == 0xF:
            if nn == 0x07: self.v[x] = self.delay_timer
            elif nn == 0x0A: self.wait_key_reg = x
            elif nn == 0x15: self.delay_timer = self.v[x]
            elif nn == 0x18: self.sound_timer = self.v[x]
            elif nn == 0x1E: self.i = (self.i + self.v[x]) & 0xFFFF
            elif nn == 0x29: self.i = 0x050 + (self.v[x] * 5)
            elif nn == 0x33:
                self.memory[self.i] = self.v[x] // 100
                self.memory[self.i+1] = (self.v[x] // 10) % 10
                self.memory[self.i+2] = self.v[x] % 10
            elif nn == 0x55:
                for idx in range(x + 1): self.memory[self.i + idx] = self.v[idx]
            elif nn == 0x65:
                for idx in range(x + 1): self.v[idx] = self.memory[self.i + idx]

    def update_timers(self):
        if self.delay_timer > 0: self.delay_timer -= 1
        if self.sound_timer > 0:
            if self.sound_timer == 1: self.bell_callback()
            self.sound_timer -= 1

class CatsEmulatorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Cat's Pure Tkinter Chip-8")
        self.root.configure(bg="#1a1a1a")
        
        # Pass the Tkinter bell function to the core
        self.chip8 = Chip8Core(bell_callback=self.root.bell)
        
        self.rom_loaded = False
        
        # Timing variables for exact 60FPS
        self.last_time = time.perf_counter()
        self.accumulator = 0.0
        self.cpu_cycles_per_frame = 10 # 10 cycles * 60 FPS = 600 Hz CPU
        
        self.setup_ui()
        self.setup_bindings()
        self.run_loop()

    def setup_ui(self):
        self.canvas = tk.Canvas(self.root, width=512, height=256, bg="black", highlightthickness=0)
        self.canvas.pack(padx=20, pady=20)
        
        btn_frame = tk.Frame(self.root, bg="#1a1a1a")
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        # STYLED BUTTON: Black background, blue text
        tk.Button(btn_frame, text="Load ROM", command=self.load_rom, 
                  bg="black", fg="#00BFFF", activebackground="#222", 
                  activeforeground="white", highlightthickness=0, bd=1).pack(pady=5)

        self.pixels = []
        for i in range(2048):
            x, y = (i % 64) * 8, (i // 64) * 8
            self.pixels.append(self.canvas.create_rectangle(x, y, x+8, y+8, fill="black", outline=""))
        self.last_gfx = bytearray(2048)

    def setup_bindings(self):
        self.root.bind('<KeyPress>', lambda e: self.set_key(e, 1))
        self.root.bind('<KeyRelease>', lambda e: self.set_key(e, 0))

    def set_key(self, event, val):
        k = event.keysym.lower()
        if k in KEY_MAP: self.chip8.key[KEY_MAP[k]] = val

    def load_rom(self):
        path = filedialog.askopenfilename()
        if path:
            with open(path, 'rb') as f: self.chip8.load_rom(f.read())
            self.rom_loaded = True
            self.last_time = time.perf_counter() # Reset time to prevent huge delta spike

    def run_loop(self):
        current_time = time.perf_counter()
        dt = current_time - self.last_time
        self.last_time = current_time

        if self.rom_loaded:
            # Prevent "spiral of death" if the window gets dragged or lags
            if dt > 0.1:
                dt = 0.1
                
            self.accumulator += dt
            frame_time = 1.0 / 60.0 # Target exactly 60 Hz

            # Run as many logical frames as needed based on actual time passed
            while self.accumulator >= frame_time:
                for _ in range(self.cpu_cycles_per_frame): 
                    self.chip8.cycle()
                self.chip8.update_timers()
                self.accumulator -= frame_time

            # Update graphics outside the accumulator to only draw the latest state
            if self.chip8.draw_flag:
                for i in range(2048):
                    if self.chip8.gfx[i] != self.last_gfx[i]:
                        color = "#39FF14" if self.chip8.gfx[i] else "black"
                        self.canvas.itemconfig(self.pixels[i], fill=color)
                        self.last_gfx[i] = self.chip8.gfx[i]
                self.chip8.draw_flag = False

        # Schedule loop fast enough to catch frame boundaries, but yield to GUI
        self.root.after(2, self.run_loop)

if __name__ == "__main__":
    root = tk.Tk()
    app = CatsEmulatorGUI(root)
    root.mainloop()
