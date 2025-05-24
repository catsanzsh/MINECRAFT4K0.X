from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
import math
import time

# Initialize Ursina with optimizations
app = Ursina(vsync=True, borderless=False, fullscreen=False)
window.size = (800, 600)
window.title = 'Minecraft Alpha v1.0.1'
window.exit_button.visible = False
window.fps_counter.enabled = True

# Game states
class GameState:
    MENU = "menu"
    PLAYING = "playing"
    PAUSED = "paused"

current_state = GameState.MENU

# Minecraft Alpha 1.0 authentic block colors
block_colors = {
    'grass': color.rgb(117, 181, 67),
    'dirt': color.rgb(134, 96, 67),
    'stone': color.rgb(125, 125, 125),
    'cobblestone': color.rgb(122, 122, 122),
    'wood': color.rgb(156, 127, 78),
    'leaves': color.rgb(87, 139, 52),
    'sand': color.rgb(218, 210, 158),
    'gravel': color.rgb(126, 124, 122),
    'coal_ore': color.rgb(115, 115, 115),
    'iron_ore': color.rgb(136, 130, 127),
    'gold_ore': color.rgb(143, 140, 125),
    'diamond_ore': color.rgb(129, 140, 143),
    'bedrock': color.rgb(85, 85, 85),
    'water': color.rgba(47, 67, 244, 128),
    'planks': color.rgb(159, 132, 77),
    'glass': color.rgba(255, 255, 255, 128)
}

# Block properties with fixed values
block_properties = {
    'sand': {'gravity': True, 'hardness': 0.5},
    'gravel': {'gravity': True, 'hardness': 0.6},
    'stone': {'gravity': False, 'hardness': 1.5},
    'dirt': {'gravity': False, 'hardness': 0.5},
    'grass': {'gravity': False, 'hardness': 0.6},
    'wood': {'gravity': False, 'hardness': 2.0},
    'leaves': {'gravity': False, 'hardness': 0.2},
    'bedrock': {'gravity': False, 'hardness': -1},
    'water': {'gravity': False, 'hardness': -1},
    'cobblestone': {'gravity': False, 'hardness': 2.0},
    'planks': {'gravity': False, 'hardness': 2.0},
    'glass': {'gravity': False, 'hardness': 0.3},
    'coal_ore': {'gravity': False, 'hardness': 3.0},
    'iron_ore': {'gravity': False, 'hardness': 3.0},
    'gold_ore': {'gravity': False, 'hardness': 3.0},
    'diamond_ore': {'gravity': False, 'hardness': 3.0},
}

# Day/Night cycle
day_time = 0
day_length = 240  # 4 minutes per day

# Block breaking
breaking_block = None
break_time = 0
break_overlay = None

# Optimized voxel class
class Voxel(Button):
    def __init__(self, position=(0,0,0), block_type='grass'):
        super().__init__(
            parent=scene,
            position=position,
            model='cube',
            origin_y=.5,
            color=block_colors.get(block_type, color.white),
            texture='white_cube' if 'ore' in block_type else 'white_cube',
            scale=1,
            collider='box'
        )
        self.block_type = block_type
        self.properties = block_properties.get(block_type, {'gravity': False, 'hardness': 1.0})
        self.falling = False
        
        # Schedule gravity check for gravity blocks
        if self.properties.get('gravity', False):
            invoke(self.check_gravity, delay=0.1)
    
    def check_gravity(self):
        if not self.properties.get('gravity', False) or self.falling:
            return
        
        # Check if there's a block below
        below_pos = self.position + Vec3(0, -1, 0)
        for entity in scene.entities:
            if isinstance(entity, Voxel) and entity.position == below_pos:
                return
        
        # No block below, start falling
        self.falling = True
        self.fall()
    
    def fall(self):
        if not self.falling:
            return
            
        # Check the position below
        below_pos = self.position + Vec3(0, -1, 0)
        
        # Check if we hit ground or another block
        hit_ground = False
        for entity in scene.entities:
            if isinstance(entity, Voxel) and entity.position == below_pos:
                hit_ground = True
                break
        
        if below_pos.y <= 0:  # Hit bedrock level
            hit_ground = True
        
        if not hit_ground:
            # Continue falling
            self.position = below_pos
            invoke(self.fall, delay=0.1)
        else:
            # Stop falling
            self.falling = False
    
    def input(self, key):
        global breaking_block, break_time, break_overlay
        
        if self.hovered and current_state == GameState.PLAYING:
            # Place blocks with right click
            if key == 'right mouse down':
                # Calculate placement position
                hit_info = raycast(camera.world_position, camera.forward, distance=5)
                if hit_info.hit and hit_info.entity == self:
                    new_pos = self.position + hit_info.normal
                    # Check if position is empty
                    position_empty = True
                    for entity in scene.entities:
                        if isinstance(entity, Voxel) and entity.position == new_pos:
                            position_empty = False
                            break
                    
                    if position_empty:
                        new_voxel = Voxel(position=new_pos, block_type=hotbar.current_block)

            # Start breaking blocks with left click
            elif key == 'left mouse down' and self.properties['hardness'] >= 0:
                breaking_block = self
                break_time = 0
                # Create break overlay
                if break_overlay:
                    destroy(break_overlay)
                break_overlay = Entity(
                    parent=scene,
                    model='cube',
                    color=color.rgba(0, 0, 0, 50),
                    position=self.position,
                    scale=1.01
                )
            
            elif key == 'left mouse up':
                # Stop breaking
                breaking_block = None
                break_time = 0
                if break_overlay:
                    destroy(break_overlay)
                    break_overlay = None

# Inventory system
class Inventory(Entity):
    def __init__(self):
        super().__init__(parent=camera.ui, enabled=False)
        
        # Dark overlay
        self.bg = Entity(
            parent=self,
            model='quad',
            color=color.rgba(0, 0, 0, 200),
            scale=(2, 2),
            z=1
        )
        
        # Inventory grid
        self.slots = []
        for row in range(4):
            for col in range(9):
                slot = Entity(
                    parent=self,
                    model='quad',
                    color=color.rgb(139, 139, 139),
                    scale=(0.08, 0.08),
                    position=(-0.32 + col * 0.08, 0.1 - row * 0.08),
                    z=0
                )
                self.slots.append(slot)
        
        # Title
        self.title = Text(
            'Inventory',
            parent=self,
            position=(0, 0.3),
            scale=2,
            color=color.white,
            origin=(0, 0)
        )

# Main Menu
class MainMenu(Entity):
    def __init__(self):
        super().__init__(parent=camera.ui)
        
        # Dirt background
        self.bg = Entity(
            parent=self,
            model='quad',
            color=color.rgb(139, 90, 43),
            scale=(2, 2),
            z=1
        )
        
        # Title with shadow
        self.title_shadow = Text(
            'Minecraft',
            parent=self,
            scale=6,
            position=(0.02, 0.28),
            origin=(0, 0),
            color=color.rgb(50, 50, 50),
            z=0
        )
        
        self.title = Text(
            'Minecraft',
            parent=self,
            scale=6,
            position=(0, 0.3),
            origin=(0, 0),
            color=color.white,
            z=-1
        )
        
        # Version
        self.version = Text(
            'Alpha v1.0.1 (Fixed)',
            parent=self,
            scale=1.5,
            position=(0, 0.15),
            origin=(0, 0),
            color=color.yellow,
            z=-1
        )
        
        # Buttons
        self.singleplayer = Button(
            text='Singleplayer',
            parent=self,
            scale=(0.4, 0.08),
            position=(0, 0),
            color=color.gray,
            on_click=self.start_game,
            z=-1
        )
        
        self.quit = Button(
            text='Quit Game',
            parent=self,
            scale=(0.4, 0.08),
            position=(0, -0.15),
            color=color.gray,
            on_click=application.quit,
            z=-1
        )
    
    def start_game(self):
        global current_state
        current_state = GameState.PLAYING
        self.enabled = False
        generate_terrain()
        mouse.locked = True
        player.enabled = True
        hotbar.ui.enabled = True
        crosshair.enabled = True
        crosshair2.enabled = True

# Hotbar
class Hotbar:
    def __init__(self):
        self.blocks = ['stone', 'grass', 'dirt', 'cobblestone', 'wood', 
                      'planks', 'sand', 'gravel', 'glass']
        self.current_index = 0
        self.current_block = self.blocks[self.current_index]
        
        # Create hotbar UI
        self.ui = Entity(parent=camera.ui, enabled=False)
        self.slots = []
        
        # Hotbar background
        self.bg = Entity(
            parent=self.ui,
            model='quad',
            color=color.rgba(100, 100, 100, 180),
            scale=(0.72, 0.08),
            position=(0, -0.45),
            z=1
        )
        
        for i, block in enumerate(self.blocks):
            # Slot background
            slot_bg = Entity(
                parent=self.ui,
                model='quad',
                color=color.white if i == 0 else color.rgb(50, 50, 50),
                scale=(0.075, 0.075),
                position=(-0.32 + i * 0.08, -0.45),
                z=0
            )
            
            # Block icon
            slot = Entity(
                parent=self.ui,
                model='cube',
                color=block_colors[block],
                scale=(0.05, 0.05, 0.05),
                position=(-0.32 + i * 0.08, -0.45),
                rotation=(20, -20, 0),
                z=-1
            )
                
            self.slots.append((slot_bg, slot))
    
    def update_selection(self):
        for i, (bg, slot) in enumerate(self.slots):
            bg.color = color.white if i == self.current_index else color.rgb(50, 50, 50)

# Terrain generation
def generate_terrain():
    # Clear existing terrain
    for entity in scene.entities[:]:
        if isinstance(entity, Voxel):
            destroy(entity)
    
    world_size = 20
    chunk_updates = []
    
    for z in range(-world_size, world_size):
        for x in range(-world_size, world_size):
            # Generate height using perlin-like noise
            height = int(4 + 3 * math.sin(x * 0.1) * math.cos(z * 0.1) + 
                        random.uniform(-1, 1))
            height = max(1, min(height, 8))
            
            # Bedrock layer
            Voxel(position=(x, 0, z), block_type='bedrock')
            
            # Generate layers
            for y in range(1, height + 1):
                if y == height:
                    Voxel(position=(x, y, z), block_type='grass')
                elif y > height - 3:
                    Voxel(position=(x, y, z), block_type='dirt')
                else:
                    # Ore generation
                    ore_chance = random.random()
                    if y < 3 and ore_chance < 0.02:
                        block = 'diamond_ore'
                    elif ore_chance < 0.05:
                        block = 'coal_ore'
                    elif ore_chance < 0.08:
                        block = 'iron_ore'
                    elif y < 8 and ore_chance < 0.1:
                        block = 'gold_ore'
                    else:
                        block = 'stone'
                    Voxel(position=(x, y, z), block_type=block)
            
            # Tree generation
            if random.random() < 0.02 and height > 4:
                trunk_height = random.randint(4, 6)
                # Trunk
                for h in range(trunk_height):
                    Voxel(position=(x, height + h + 1, z), block_type='wood')
                
                # Leaves
                leaf_start = height + trunk_height - 1
                for ly in range(3):
                    for lx in range(-2, 3):
                        for lz in range(-2, 3):
                            if abs(lx) + abs(lz) <= 3 - ly:
                                if not (lx == 0 and lz == 0 and ly < 2):
                                    Voxel(position=(x + lx, leaf_start + ly, z + lz), 
                                         block_type='leaves')

# Set up scene
scene.fog_color = color.rgb(198, 215, 251)
scene.fog_density = 0.02
sky = Sky()

# Player
player = FirstPersonController(
    position=(0, 10, 0),
    speed=4.3,
    jump_height=1.25,
    jump_duration=0.25,
    gravity=1.0,
    enabled=False,
    mouse_sensitivity=Vec2(40, 40)
)

# UI elements
hotbar = Hotbar()
main_menu = MainMenu()
inventory = Inventory()

# Crosshair
crosshair = Entity(
    parent=camera.ui,
    model='quad',
    color=color.white,
    scale=(0.008, 0.01),
    position=(0, 0),
    enabled=False
)
crosshair2 = Entity(
    parent=camera.ui,
    model='quad',
    color=color.white,
    scale=(0.01, 0.008),
    position=(0, 0),
    enabled=False
)

# Update function
def update():
    global day_time, breaking_block, break_time, break_overlay
    
    if current_state == GameState.PLAYING:
        # Day/night cycle
        day_time += time.dt / day_length
        if day_time > 1:
            day_time = 0
        
        # Sky color based on time
        if day_time < 0.25:  # Morning
            t = day_time * 4
            sky.color = color.rgb(
                int(20 + 115 * t),
                int(24 + 182 * t),
                int(82 + 153 * t)
            )
            scene.fog_color = sky.color
            
        elif day_time < 0.5:  # Day
            sky.color = color.rgb(135, 206, 235)
            scene.fog_color = color.rgb(198, 215, 251)
            
        elif day_time < 0.75:  # Evening
            t = (day_time - 0.5) * 4
            sky.color = color.rgb(
                int(135 + 120 * t),
                int(206 - 112 * t),
                int(235 - 158 * t)
            )
            scene.fog_color = sky.color
            
        else:  # Night
            sky.color = color.rgb(20, 24, 82)
            scene.fog_color = color.rgb(20, 24, 82)
        
        # Block breaking
        if breaking_block and mouse.left:
            break_time += time.dt
            hardness = breaking_block.properties['hardness']
            
            if hardness > 0 and break_time >= hardness:
                # Break the block
                if breaking_block.position[1] > 0:  # Don't break bedrock
                    # Check for gravity blocks above
                    above_pos = breaking_block.position + Vec3(0, 1, 0)
                    for entity in scene.entities:
                        if isinstance(entity, Voxel) and entity.position == above_pos:
                            if entity.properties.get('gravity', False):
                                entity.check_gravity()
                    
                    destroy(breaking_block)
                    
                breaking_block = None
                break_time = 0
                if break_overlay:
                    destroy(break_overlay)
                    break_overlay = None
            else:
                # Update break overlay
                if break_overlay:
                    progress = break_time / hardness if hardness > 0 else 0
                    break_overlay.color = color.rgba(0, 0, 0, int(50 + 150 * progress))

# Input handler
def input(key):
    global current_state, breaking_block, break_time, break_overlay
    
    if key == 'escape':
        if current_state == GameState.PLAYING:
            # Return to menu
            current_state = GameState.MENU
            mouse.locked = False
            player.enabled = False
            main_menu.enabled = True
            hotbar.ui.enabled = False
            crosshair.enabled = False
            crosshair2.enabled = False
            inventory.enabled = False
            # Clear breaking state
            breaking_block = None
            break_time = 0
            if break_overlay:
                destroy(break_overlay)
                break_overlay = None
        else:
            application.quit()
    
    if current_state == GameState.PLAYING:
        # Inventory toggle
        if key == 'e':
            inventory.enabled = not inventory.enabled
            mouse.locked = not inventory.enabled
        
        # Hotbar selection
        if key in '123456789':
            idx = int(key) - 1
            if idx < len(hotbar.blocks):
                hotbar.current_index = idx
                hotbar.current_block = hotbar.blocks[idx]
                hotbar.update_selection()
        
        # Scroll hotbar
        if key == 'scroll up':
            hotbar.current_index = (hotbar.current_index - 1) % len(hotbar.blocks)
            hotbar.current_block = hotbar.blocks[hotbar.current_index]
            hotbar.update_selection()
        elif key == 'scroll down':
            hotbar.current_index = (hotbar.current_index + 1) % len(hotbar.blocks)
            hotbar.current_block = hotbar.blocks[hotbar.current_index]
            hotbar.update_selection()
        
        # Sprint
        if key == 'left shift':
            player.speed = 6.5
        elif key == 'left shift up':
            player.speed = 4.3

# Run the game
if __name__ == '__main__':
    app.run()
