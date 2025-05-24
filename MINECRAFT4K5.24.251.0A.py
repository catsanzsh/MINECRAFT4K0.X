from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
import math
import time

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
BEDROCK = 4  # Added bedrock as an indestructible block

# Chunk settings
CHUNK_SIZE = 16
chunks = {}

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
        # Calculate terrain height at current position
        chunk_x = math.floor(self.x / CHUNK_SIZE)
        chunk_z = math.floor(self.z / CHUNK_SIZE)
        local_x = (math.floor(self.x) % CHUNK_SIZE + CHUNK_SIZE) % CHUNK_SIZE
        local_z = (math.floor(self.z) % CHUNK_SIZE + CHUNK_SIZE) % CHUNK_SIZE
        terrain_height = get_terrain_height(chunk_x, chunk_z, local_x, local_z)
        # Check if item has reached or passed the terrain surface
        if self.y <= terrain_height + 1:
            self.y = terrain_height + 1  # Place on top of terrain
            self.grounded = True
            self.fall_speed = 0
        else:
            self.fall_speed -= 0.1  # Apply gravity
            self.y += self.fall_speed * time.dt * 10

# Chunk class for voxel data and mesh
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
                height = int(random.uniform(0, 3))
                for y in range(CHUNK_SIZE):
                    if y == 0:
                        self.voxels[x][y][z] = BEDROCK  # Bottom layer is bedrock
                    elif y < height:
                        self.voxels[x][y][z] = DIRT
                    elif y == height and random.random() < 0.2:
                        self.voxels[x][y][z] = WATER
                    elif y == height + 1 and random.random() < 0.1:
                        self.voxels[x][y][z] = GLASS
    
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
                        (x+1, y, z), (x-1, y, z),  # Right, Left
                        (x, y+1, z), (x, y-1, z),  # Top, Bottom
                        (x, y, z+1), (x, y, z-1)  # Front, Back
                    ]
                    for i, (nx, ny, nz) in enumerate(neighbors):
                        if not (0 <= nx < CHUNK_SIZE and 0 <= ny < CHUNK_SIZE and 0 <= nz < CHUNK_SIZE):
                            neighbor_block = get_block(nx + self.chunk_x * CHUNK_SIZE, ny, nz + self.chunk_z * CHUNK_SIZE)
                        else:
                            neighbor_block = self.voxels[nx][ny][nz]
                        if neighbor_block == AIR or (block == WATER and neighbor_block != WATER) or (block == GLASS and neighbor_block != GLASS):
                            # Define vertices for all faces
                            face_vertices = [
                                # Front (z+1)
                                Vec3(x, y, z+1), Vec3(x+1, y, z+1), Vec3(x+1, y+1, z+1), Vec3(x, y+1, z+1),
                                # Back (z)
                                Vec3(x+1, y, z), Vec3(x, y, z), Vec3(x, y+1, z), Vec3(x+1, y+1, z),
                                # Right (x+1)
                                Vec3(x+1, y, z+1), Vec3(x+1, y, z), Vec3(x+1, y+1, z), Vec3(x+1, y+1, z+1),
                                # Left (x)
                                Vec3(x, y, z), Vec3(x, y, z+1), Vec3(x, y+1, z+1), Vec3(x, y+1, z),
                                # Top (y+1)
                                Vec3(x, y+1, z), Vec3(x+1, y+1, z), Vec3(x+1, y+1, z+1), Vec3(x, y+1, z+1),
                                # Bottom (y)
                                Vec3(x, y, z), Vec3(x+1, y, z), Vec3(x+1, y, z+1), Vec3(x, y, z+1)
                            ]
                            # Select the 4 vertices for the current face
                            fv = face_vertices[i*4:i*4+4]
                            face_color = (
                                color.brown if block == DIRT else
                                color.blue if block == WATER else
                                color.clear if block == GLASS else
                                color.gray if block == BEDROCK else
                                color.white
                            )
                            # Add vertices and colors
                            for vi in fv:
                                vertices.append(vi + Vec3(self.chunk_x * CHUNK_SIZE, 0, self.chunk_z * CHUNK_SIZE))
                                colors.append(face_color)
                            # Add triangles with correct indices for this face
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
    chunk.voxels[local_x][local_y][local_z] = block_type
    chunk.rebuild_mesh()
    if old_block != AIR and block_type == AIR:
        Item(position=(x, y + 0.5, z))

# Player setup and initial chunks
for cx in range(-2, 3):
    for cz in range(-2, 3):
        chunks[(cx, cz)] = Chunk(cx, cz)

player = FirstPersonController()
terrain_height = get_terrain_height(0, 0, 0, 0)
player.position = (0, terrain_height + 2, 0)

# Input handling
def input(key):
    global game_state
    if key == 'space' and game_state == STATE_MENU:
        game_state = STATE_PLAYING
        menu_text.enabled = False
    elif key == 'left mouse down' and game_state == STATE_PLAYING:
        hit_info = raycast(player.position, player.forward, distance=5)
        if hit_info.hit and hit_info.entity in [chunk for chunk in chunks.values()]:
            x, y, z = [math.floor(v) for v in hit_info.world_point]
            set_block(x, y, z, DIRT)
    elif key == 'right mouse down' and game_state == STATE_PLAYING:
        hit_info = raycast(player.position, player.forward, distance=5)
        if hit_info.hit and hit_info.entity in [chunk for chunk in chunks.values()]:
            x, y, z = [math.floor(v) for v in hit_info.world_point]
            if get_block(x, y, z) != BEDROCK:  # Prevent destroying bedrock
                set_block(x, y, z, AIR)

# Run the app
app.run()
