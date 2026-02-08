from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
import time
from perlin_noise import PerlinNoise

app = Ursina()

# --- Configuration ---
WORLD_SIZE = 16  # 16x16 grid (256 blocks base)
MAX_HEIGHT = 8
SENSITIVITY = 40
pnoise = PerlinNoise()

# --- Textures/Colors ---
block_colors = [color.green, color.dark_gray, color.gray]
LEAF_COLOR = color.rgb(0.35, 0.52, 0.3)   # greenish-gray (distinct from hotbar)
HOTBAR_COLOR = color.rgb(0.42, 0.42, 0.48)  # slightly blue-tinted grey

# --- Inventory ---
inventory = {'grass': 0, 'stone': 0, 'wood': 0, 'leaves': 0}
slot_order = []  # Order items were first collected (max 4)

ITEM_COLORS = {'grass': color.green, 'stone': color.dark_gray, 'wood': color.brown, 'leaves': LEAF_COLOR}

def get_item_from_block(col):
    """Map block color to item name for inventory."""
    if col == color.green:
        return 'grass'
    elif col == color.dark_gray:
        return 'stone'
    elif col == color.brown:
        return 'wood'
    elif col == LEAF_COLOR:
        return 'leaves'
    return None

class Voxel(Button):
    def __init__(self, position=(0,0,0), col=color.white):
        super().__init__(
            parent=scene,
            position=position,
            model='cube',
            origin_y=0.5,
            texture='white_cube',
            color=col,
            highlight_color=col,
        )
        self.col = col
        self.original_scale = 1.0
        self.breaking_start_time = None
        self.set_hardness()

    def get_distance_to_camera(self):
        return distance(self.world_position, camera.world_position)
    
    def is_in_reach(self):
        return self.get_distance_to_camera() <= 7

    def set_hardness(self):
        # Hardness in seconds based on block type (density)
        if self.col == color.green:  # Grass
            self.hardness = 0.3
        elif self.col == color.dark_gray:  # Stone
            self.hardness = 1.2
        elif self.col == color.brown:  # Wood
            self.hardness = 0.5
        elif self.col == LEAF_COLOR:  # Leaves
            self.hardness = 0.2
        else:  # Default white blocks
            self.hardness = 0.6

    def input(self, key):
        if self.hovered and self.is_in_reach():
            # Left Click to BREAK
            if key == 'left mouse down':
                self.breaking_start_time = time.time()
            
            if key == 'left mouse up':
                self.breaking_start_time = None
            
            # Right Click to PLACE
            if key == 'right mouse down':
                Voxel(position=self.position + mouse.normal, col=self.col)

    def update(self):
        # Show hover effect only if in reach
        if self.hovered and self.is_in_reach():
            self.color = color.yellow
        elif self.breaking_start_time is None:
            self.color = self.col
            
        if self.breaking_start_time is not None:
            elapsed = time.time() - self.breaking_start_time
            progress = elapsed / self.hardness
            
            # Visual breaking effect - scale down as progress increases
            if progress >= 1.0:
                item = get_item_from_block(self.col)
                if item:
                    inventory[item] += 1
                    if item not in slot_order and len(slot_order) < 4:
                        slot_order.append(item)
                destroy(self)
            else:
                # Shrink block based on breaking progress (80% to 100% size)
                self.scale = 0.8 + (0.2 * (1 - progress))
        else:
            # Reset scale when not breaking
            self.scale = 1.0

# --- World Generation ---
def generate_world():
    for z in range(WORLD_SIZE):
        for x in range(WORLD_SIZE):
            # Generate hills using Perlin Noise
            # We scale the coordinates to make the hills "smoother"
            noise_val = pnoise((x * 0.1, z * 0.1))
            height = floor((noise_val + 1) * MAX_HEIGHT)
            
            for y in range(height):
                # Color based on height (Green top, Gray bottom)
                block_color = color.green if y == height - 1 else color.dark_gray
                Voxel(position=(x, y, z), col=block_color)

            # Random Tree Generation (approx 2% chance on surface)
            if random.random() < 0.02:
                generate_tree(x, height, z)

def generate_tree(x, y, z):
    # Trunk
    for i in range(3):
        Voxel(position=(x, y + i, z), col=color.brown)
    # Leaves
    for lx in range(-1, 2):
        for lz in range(-1, 2):
            Voxel(position=(x + lx, y + 3, z + lz), col=LEAF_COLOR)

generate_world()

# --- Player Logic ---
player = FirstPersonController()
player.cursor.visible = True
player.speed = 5

selected_slot = 0

# --- Selection Border ---
# Create 4 border entities, one for each slot
selection_borders = []
for i in range(4):
    x_pos = -0.5 + (i + 0.5) / 5
    border = Entity(
        parent=hotbar,
        model='quad',
        scale=(0.17, 1.05),
        position=(x_pos, 0),
        color=color.white,
        z=-0.03,
    )
    border.enabled = False
    selection_borders.append(border)

def update_selection_border():
    for i, border in enumerate(selection_borders):
        border.enabled = (i == selected_slot)

def input(key):
    global selected_slot

    if key == 'f11':
        window.fullscreen = not window.fullscreen

    # Number keys 1-4 to select hotbar slots
    if key in ['1', '2', '3', '4']:
        selected_slot = int(key) - 1
        update_selection_border()

    # Right click to place block from selected slot
    if key == 'right mouse down':
        if selected_slot < len(slot_order):
            item = slot_order[selected_slot]
            if inventory.get(item, 0) > 0:
                # Get the color for this item
                col = ITEM_COLORS.get(item, color.white)
                # Place block at position + normal
                Voxel(position=mouse.position + mouse.normal, col=col)
                # Decrease inventory
                inventory[item] -= 1

def update():
    # Sprinting logic with Shift
    if held_keys['shift']:
        player.speed = 10
    else:
        player.speed = 5

    # Update hotbar slot icons (show item when collected)
    update_hotbar_slots()

# --- Hotbar UI ---
hotbar = Panel(
    parent=camera.ui,
    scale=(0.8, 0.25),
    position=(0, -0.48),
    color=HOTBAR_COLOR,
    border_color=color.rgb(0.3, 0.3, 0.3),
    border_size=0.002,
    border_radius=0
)

# 4 vertical dividers splitting hotbar into 5 sections
# Parent to hotbar so they align; use hotbar's local coords (-0.5 to 0.5)
for i in range(1, 5):
    x_pos = -0.5 + (i / 5)  # -0.3, -0.1, 0.1, 0.3
    Entity(
        parent=hotbar,
        model='quad',
        scale=(0.03, 1.1),  # thicker so visible, slightly taller than hotbar
        position=(x_pos, 0),
        color=color.rgb(0.15, 0.15, 0.15),
        z=-0.01  # render in front of hotbar panel
    )

# Hotbar slot icons - show items in order they were first collected
# Slot centers in screen space (hotbar at 0,-0.48, scale 0.8,0.25)
SLOT_SCREEN_X = [-0.32, -0.16, 0, 0.16]  # approx centers of 4 slots
HOTBAR_SCREEN_Y = -0.46

hotbar_slot_icons = []
for i in range(4):
    x_pos = -0.5 + (i + 0.5) / 5  # center of each slot
    icon = Entity(
        parent=hotbar,
        model='quad',
        scale=(0.15, 0.8),
        position=(x_pos, 0),
        color=color.white,  # set dynamically
        z=-0.02,
    )
    icon.slot_index = i
    # Count on camera.ui so scale isn't squished by hotbar
    count_text = Text(
        parent=camera.ui,
        text='',
        position=(SLOT_SCREEN_X[i], HOTBAR_SCREEN_Y),
        origin=(0.5, 0.5),
        scale=2.5,
        color=color.black,
        z=0.5,
    )
    icon.count_text = count_text
    hotbar_slot_icons.append(icon)

def update_hotbar_slots():
    """Show slot icons and counts (number only, hide if 0)."""
    for icon in hotbar_slot_icons:
        if icon.slot_index < len(slot_order):
            item = slot_order[icon.slot_index]
            count = inventory.get(item, 0)
            icon.enabled = count > 0
            icon.color = ITEM_COLORS.get(item, color.white)
            icon.count_text.enabled = count > 0
            icon.count_text.text = str(count) if count > 0 else ''
        else:
            icon.enabled = False
            icon.count_text.enabled = False

app.run()
