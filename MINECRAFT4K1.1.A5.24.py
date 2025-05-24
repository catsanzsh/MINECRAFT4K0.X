from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from perlin_noise import PerlinNoise
import random
import math
import time
from ursina import Vec3  # Added import for Vec3

# Initialize Ursina app
app = Ursina()

# Game states
STATE_MENU = 0
STATE_PLAYING = 1
game_state = STATE_MENU

# Menu text
menu_text = Text(
    text="Press SPACE to start",
    position=(0, 0),
    scale=2,
    origin=(0, 0),
    background=True
)

# Block types
AIR = 0
DIRT = 1
WATER = 2
GLASS = 3
BEDROCK = 4
STONE = 5
GRASS = 6
WOOD = 7
SAND = 8
GRAVEL = 9
LEAVES = 10
LOG = 11

# Chunk settings
CHUNK_SIZE = 16
chunks = {}

# Falling block types
falling_blocks = {SAND, GRAVEL}

# Perlin noise for terrain generation
noise = PerlinNoise(octaves=4, seed=random.randint(0, 1000))

# Biome types
BIOME_PLAINS = 0
BIOME_FOREST = 1
BIOME_DESERT = 2

# Function to determine biome
def get_biome(x, z):
    biome_noise = noise([x / 100, z / 100])
    if biome_noise < -0.1:
        return BIOME_DESERT
    elif biome_noise > 0.1:
        return BIOME_FOREST
    else:
        return BIOME_PLAINS

# Function to get block color
def get_block_color(block):
    if block == DIRT:
        return color.brown
    elif block == WATER:
        return color.blue
    elif block == GLASS:
        return color.clear
    elif block == BEDROCK:
        return color.gray
    elif block == STONE:
        return color.dark_gray
    elif block == GRASS:
        return color.green
    elif block == WOOD:
        return color.orange
    elif block == SAND:
        return color.yellow
    elif block == GRAVEL:
        return color.light_gray
    elif block == LEAVES:
        return color.lime
    elif block == LOG:
        return color.brown
    else:
        return color.white

# Item class for dropped items
class Item(Entity):
    def __init__(self, position):
        super().__init__(
            model='cube',
            scale=0.5,
            color=color.yellow,
            position=position
        )
        self.fall_speed = 0
        self.grounded = False
    
    def update(self):
        chunk_x = math.floor(self.x / CHUNK_SIZE)
        chunk_z = math.floor(self.z / CHUNK_SIZE)
        local_x = (math.floor(self.x) % CHUNK_SIZE + CHUNK_SIZE) % CHUNK_SIZE
        local_z = (math.floor(self.z) % CHUNK_SIZE + CHUNK_SIZE) % CHUNK_SIZE
        terrain_height = get_terrain_height(chunk_x, chunk_z, local_x, local_z)
        if self.y <= terrain_height + 1:
            self.y = terrain_height + 1
            self.grounded = True
            self.fall_speed = 0
        else:
            self.fall_speed -= 0.1
            self.y += self.fall_speed * time.dt * 10

# FallingBlock class
class FallingBlock(Entity):
    def __init__(self, position, block_type):
        super().__init__(
            model='cube',
            color=get_block_color(block_type),
            position=position
        )
        self.block_type = block_type
        self.fall_speed = 0
    
    def update(self):
        chunk_x = math.floor(self.x / CHUNK_SIZE)
        chunk_z = math.floor(self.z / CHUNK_SIZE)
        local_x = (math.floor(self.x) % CHUNK_SIZE + CHUNK_SIZE) % CHUNK_SIZE
        local_z = (math.floor(self.z) % CHUNK_SIZE + CHUNK_SIZE) % CHUNK_SIZE
        landing_y = get_terrain_height(chunk_x, chunk_z, local_x, local_z) + 1
        if self.y <= landing_y:
            self.y = landing_y
            set_block(math.floor(self.x), landing_y, math.floor(self.z), self.block_type)
            destroy(self)
        else:
            self.fall_speed -= 0.1
            self.y += self.fall_speed * time.dt * 10

# Mob class (simple wandering entity) - FIXED
class Mob(Entity):
    def __init__(self, position):
        super().__init__(
            model='cube',
            color=color.white,
            scale=1,
            position=position
        )
        # Use Vec3 instead of tuples
        self.direction = random.choice([Vec3(1,0,0), Vec3(-1,0,0), Vec3(0,0,1), Vec3(0,0,-1)])
        self.speed = 2
    
    def update(self):
        # Vec3 allows multiplication by floats
        self.position += self.direction * self.speed * time.dt
        if random.random() < 0.01:  # Randomly change direction
            self.direction = random.choice([Vec3(1,0,0), Vec3(-1,0,0), Vec3(0,0,1), Vec3(0,0,-1)])

# Chunk class
class Chunk(Entity):
    def __init__(self, chunk_x, chunk_z):
        super().__init__()
        self.chunk_x = chunk_x
        self.chunk_z = chunk_z
        self.voxels = [[[AIR for _ in range(CHUNK_SIZE)] for _ in range(CHUNK_SIZE)] for _ in range(CHUNK_SIZE)]
        self.model = None
        self.collider = None
        self.generate_voxels()
        self.rebuild_mesh()
    
    def generate_voxels(self):
        for x in range(CHUNK_SIZE):
            for z in range(CHUNK_SIZE):
                world_x = self.chunk_x * CHUNK_SIZE + x
                world_z = self.chunk_z * CHUNK_SIZE + z
                biome = get_biome(world_x, world_z)
                height = int((noise([world_x / 50, world_z / 50]) + 1) * 5) + 5
                for y in range(CHUNK_SIZE):
                    if y == 0:
                        self.voxels[x][y][z] = BEDROCK
                    elif y < height - 3:
                        self.voxels[x][y][z] = STONE
                    elif y < height:
                        if biome == BIOME_DESERT:
                            self.voxels[x][y][z] = SAND
                        else:
                            self.voxels[x][y][z] = DIRT
                    elif y == height:
                        if biome == BIOME_DESERT:
                            self.voxels[x][y][z] = SAND
                        elif biome == BIOME_FOREST:
                            self.voxels[x][y][z] = GRASS
                            if random.random() < 0.1:  # 10% chance for a tree
                                self.generate_tree(x, y, z)
                        else:
                            self.voxels[x][y][z] = GRASS
                    else:
                        self.voxels[x][y][z] = AIR
    
    def generate_tree(self, x, y, z):
        # Simple tree: 3 logs high with a 3x3 leaf canopy
        for yy in range(y, y + 3):
            if yy < CHUNK_SIZE:
                self.voxels[x][yy][z] = LOG
        for xx in range(x - 1, x + 2):
            for zz in range(z - 1, z + 2):
                if 0 <= xx < CHUNK_SIZE and 0 <= zz < CHUNK_SIZE and y + 3 < CHUNK_SIZE:
                    self.voxels[xx][y + 3][zz] = LEAVES
    
    def rebuild_mesh(self):
        vertices = []
        triangles = []
        colors = []
        vertex_count = 0
        
        for x in range(CHUNK_SIZE):
            for y in range(CHUNK_SIZE):
                for z in range(CHUNK_SIZE):
                    block = self.voxels[x][y][z]
                    if block == AIR:
                        continue
                    neighbors = [
                        (x+1, y, z), (x-1, y, z),
                        (x, y+1, z), (x, y-1, z),
                        (x, y, z+1), (x, y, z-1)
                    ]
                    for i, (nx, ny, nz) in enumerate(neighbors):
                        if not (0 <= nx < CHUNK_SIZE and 0 <= ny < CHUNK_SIZE and 0 <= nz < CHUNK_SIZE):
                            neighbor_block = get_block(nx + self.chunk_x * CHUNK_SIZE, ny, nz + self.chunk_z * CHUNK_SIZE)
                        else:
                            neighbor_block = self.voxels[nx][ny][nz]
                        if neighbor_block == AIR or (block == WATER and neighbor_block != WATER) or (block == GLASS and neighbor_block != GLASS):
                            face_vertices = [
                                Vec3(x, y, z+1), Vec3(x+1, y, z+1), Vec3(x+1, y+1, z+1), Vec3(x, y+1, z+1),
                                Vec3(x+1, y, z), Vec3(x, y, z), Vec3(x, y+1, z), Vec3(x+1, y+1, z),
                                Vec3(x+1, y, z+1), Vec3(x+1, y, z), Vec3(x+1, y+1, z), Vec3(x+1, y+1, z+1),
                                Vec3(x, y, z), Vec3(x, y, z+1), Vec3(x, y+1, z+1), Vec3(x, y+1, z),
                                Vec3(x, y+1, z), Vec3(x+1, y+1, z), Vec3(x+1, y+1, z+1), Vec3(x, y+1, z+1),
                                Vec3(x, y, z), Vec3(x+1, y, z), Vec3(x+1, y, z+1), Vec3(x, y, z+1)
                            ]
                            fv = face_vertices[i*4:i*4+4]
                            face_color = get_block_color(block)
                            for vi in fv:
                                vertices.append(vi + Vec3(self.chunk_x * CHUNK_SIZE, 0, self.chunk_z * CHUNK_SIZE))
                                colors.append(face_color)
                            triangles.append([vertex_count, vertex_count+1, vertex_count+2])
                            triangles.append([vertex_count+2, vertex_count+3, vertex_count])
                            vertex_count += 4
        
        self.model = Mesh(vertices=vertices, triangles=triangles, colors=colors, mode='triangle')
        self.collider = 'mesh'
        self.position = (self.chunk_x * CHUNK_SIZE, 0, self.chunk_z * CHUNK_SIZE)

# Helper functions
def get_terrain_height(chunk_x, chunk_z, local_x, local_z):
    chunk = chunks.get((chunk_x, chunk_z))
    if not chunk:
        return 0
    for y in range(CHUNK_SIZE-1, -1, -1):
        if chunk.voxels[local_x][y][local_z] != AIR:
            return y
    return 0

def get_block(x, y, z):
    chunk_x = math.floor(x / CHUNK_SIZE)
    chunk_z = math.floor(z / CHUNK_SIZE)
    local_x = (x % CHUNK_SIZE + CHUNK_SIZE) % CHUNK_SIZE
    local_y = y
    local_z = (z % CHUNK_SIZE + CHUNK_SIZE) % CHUNK_SIZE
    chunk = chunks.get((chunk_x, chunk_z))
    if not chunk or local_y < 0 or local_y >= CHUNK_SIZE:
        return AIR
    return chunk.voxels[local_x][local_y][local_z]

def set_block(x, y, z, block_type):
    chunk_x = math.floor(x / CHUNK_SIZE)
    chunk_z = math.floor(z / CHUNK_SIZE)
    local_x = (x % CHUNK_SIZE + CHUNK_SIZE) % CHUNK_SIZE
    local_y = y
    local_z = (z % CHUNK_SIZE + CHUNK_SIZE) % CHUNK_SIZE
    if local_y < 0 or local_y >= CHUNK_SIZE:
        return
    chunk = chunks.get((chunk_x, chunk_z))
    if not chunk:
        chunk = Chunk(chunk_x, chunk_z)
        chunks[(chunk_x, chunk_z)] = chunk
    old_block = chunk.voxels[local_x][local_y][local_z]
    if block_type in falling_blocks and get_block(x, y-1, z) == AIR:
        FallingBlock(position=(x, y, z), block_type=block_type)
    else:
        chunk.voxels[local_x][local_y][local_z] = block_type
        chunk.rebuild_mesh()
    if block_type == AIR:
        for yy in range(local_y + 1, CHUNK_SIZE):
            if chunk.voxels[local_x][yy][local_z] in falling_blocks and chunk.voxels[local_x][yy-1][local_z] == AIR:
                fb_type = chunk.voxels[local_x][yy][local_z]
                chunk.voxels[local_x][yy][local_z] = AIR
                FallingBlock(position=(x, yy, z), block_type=fb_type)
            else:
                break
        chunk.rebuild_mesh()
    if old_block != AIR and block_type == AIR:
        Item(position=(x, y + 0.5, z))

# Player setup and initial chunks
for cx in range(-2, 3):
    for cz in range(-2, 3):
        chunks[(cx, cz)] = Chunk(cx, cz)

# Spawn a few mobs
for _ in range(5):
    Mob(position=(random.randint(-20, 20), 10, random.randint(-20, 20)))

player = FirstPersonController()
terrain_height = get_terrain_height(0, 0, 0, 0)
player.position = (0, terrain_height + 2, 0)

# Selected block type
selected_block = DIRT

# Input handling
def input(key):
    global game_state, selected_block
    if key == 'space' and game_state == STATE_MENU:
        game_state = STATE_PLAYING
        menu_text.enabled = False
    elif key == '1':
        selected_block = DIRT
    elif key == '2':
        selected_block = SAND
    elif key == '3':
        selected_block = GRAVEL
    elif key == 'left mouse down' and game_state == STATE_PLAYING:
        hit_info = raycast(player.position, player.forward, distance=5)
        if hit_info.hit and hit_info.entity in [chunk for chunk in chunks.values()]:
            targeted_pos = [math.floor(v) for v in hit_info.world_point]
            block_type = get_block(*targeted_pos)
            if block_type != AIR and block_type != BEDROCK:
                set_block(*targeted_pos, AIR)
    elif key == 'right mouse down' and game_state == STATE_PLAYING:
        hit_info = raycast(player.position, player.forward, distance=5)
        if hit_info.hit and hit_info.entity in [chunk for chunk in chunks.values()]:
            targeted_pos = [math.floor(v) for v in hit_info.world_point]
            direction = [round(n) for n in hit_info.normal]
            new_pos = [t + d for t, d in zip(targeted_pos, direction)]
            if get_block(*new_pos) == AIR:
                set_block(*new_pos, selected_block)

# Run the app
app.run()
