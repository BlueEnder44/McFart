from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
from perlin_noise import PerlinNoise
import winsound
import random

app = Ursina()

# Configuration
WORLD_SIZE = 24  # Reduced from 32 for better performance
MAX_HEIGHT = 8   # Reduced from 10
RENDER_DISTANCE = 16  # Only render blocks within 16 blocks of player
pnoise = PerlinNoise()

# Store all voxels for culling
all_voxels = []

# 9-slot hotbar palette (Minecraft-like)
HOTBAR_PALETTE = ['grass','stone','wood','leaves','dirt','sand','cobble','glass','brick','cactus']

# Simple color map for the 9 items
LEAF_COLOR = color.rgb(0.35, 0.52, 0.3)
WOOD_COLOR = color.rgb(0.6, 0.4, 0.2)  # Distinct wood color
CACTUS_COLOR = color.rgb(0.2, 0.6, 0.2)  # Green cactus color
SAND_COLOR = color.rgb(0.93, 0.87, 0.68)  # Sandy color
ITEM_COLORS = {
    'grass': color.green,
    'stone': color.dark_gray,
    'wood': WOOD_COLOR,
    'leaves': LEAF_COLOR,
    'dirt': color.brown,
    'sand': SAND_COLOR,
    'cobble': color.gray,
    'glass': color.cyan,
    'brick': color.red,
    'cactus': CACTUS_COLOR,
}

# 9 slots holding {type, count}
hotbar_slots = [{ 'type': None, 'count': 0 } for _ in range(9)]
selected_slot = 0

MAX_STACK_SIZE = 64

def add_to_hotbar(item):
    # add to existing stack (up to max)
    for s in hotbar_slots:
        if s['type'] == item and s['count'] < MAX_STACK_SIZE:
            s['count'] += 1
            return
    # add to first empty slot
    for s in hotbar_slots:
        if s['type'] is None:
            s['type'] = item
            s['count'] = 1
            return

class BreakingParticle(Entity):
    def __init__(self, position, color):
        super().__init__(
            parent=scene,
            model='cube',
            position=position,
            color=color,
            scale=0.15
        )
        self.velocity = Vec3(
            random.uniform(-0.1, 0.1),
            random.uniform(0.1, 0.3),
            random.uniform(-0.1, 0.1)
        )
        self.life = 0.5
        self.age = 0
    
    def update(self):
        self.age += time.dt
        self.position += self.velocity * time.dt
        self.velocity.y -= 0.5 * time.dt  # gravity
        self.scale *= 0.95
        if self.age >= self.life:
            destroy(self)

def spawn_breaking_particles(position, color):
    # Reduced from 8 to 4 particles for better performance
    for _ in range(4):
        BreakingParticle(position + Vec3(random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3), random.uniform(-0.3, 0.3)), color)

# List to track dropped items
dropped_items = []

def get_block_at_position(pos):
    """Check if there's a voxel block at the given position."""
    check_pos = Vec3(round(pos.x), round(pos.y), round(pos.z))
    for entity in scene.children:
        if isinstance(entity, Voxel):
            entity_pos = Vec3(round(entity.position.x), round(entity.position.y), round(entity.position.z))
            if entity_pos == check_pos:
                return entity
    return None

class ItemEntity(Entity):
    def __init__(self, position, item_type):
        super().__init__(
            parent=scene,
            model='cube',
            position=position,
            color=ITEM_COLORS.get(item_type, color.white),
            scale=0.25
        )
        self.item_type = item_type
        self.velocity = Vec3(
            random.uniform(-0.05, 0.05),
            random.uniform(0.2, 0.4),
            random.uniform(-0.05, 0.05)
        )
        self.bounce = 0.5
        self.grounded = False
        self.life = 300  # 5 minutes before despawning (at 60fps)
        self.picked_up = False
        dropped_items.append(self)
    
    def update(self):
        if self.picked_up:
            return
        
        # Only update physics every 2nd frame for performance
        if frame_count % 2 != 0 and self.grounded:
            # Just rotate if grounded and on even frames
            self.rotation_y += 90 * time.dt
            return
            
        # Physics
        if not self.grounded:
            self.position += self.velocity * time.dt
            self.velocity.y -= 1.0 * time.dt  # gravity
            
            # Check for block collision below
            check_pos_below = Vec3(self.position.x, self.position.y - 0.125, self.position.z)
            block_below = get_block_at_position(check_pos_below)
            
            if block_below:
                # Land on top of the block
                target_y = block_below.position.y + 0.625  # Block height (0.5) + item half-height (0.125)
                if self.position.y <= target_y:
                    self.position.y = target_y
                    self.velocity.y = -self.velocity.y * self.bounce
                    self.velocity.x *= 0.8
                    self.velocity.z *= 0.8
                    if abs(self.velocity.y) < 0.1:
                        self.grounded = True
                        self.velocity = Vec3(0, 0, 0)
            elif self.position.y <= 0.125:
                # Hit the ground
                self.position.y = 0.125
                self.velocity.y = -self.velocity.y * self.bounce
                self.velocity.x *= 0.8
                self.velocity.z *= 0.8
                if abs(self.velocity.y) < 0.1:
                    self.grounded = True
                    self.velocity = Vec3(0, 0, 0)
        
        # Rotate slowly
        self.rotation_y += 90 * time.dt
        
        # Check for player pickup (only every 5 frames for performance)
        if frame_count % 5 == 0:
            try:
                player_pos = player.position
                dist = distance(self.position, player_pos)
                if dist <= 2.0:  # Within 2 blocks
                    # Try to add to hotbar
                    added = False
                    for s in hotbar_slots:
                        if s['type'] == self.item_type and s['count'] < MAX_STACK_SIZE:
                            s['count'] += 1
                            added = True
                            break
                    if not added:
                        for s in hotbar_slots:
                            if s['type'] is None:
                                s['type'] = self.item_type
                                s['count'] = 1
                                added = True
                                break
                    
                    if added:
                        self.picked_up = True
                        destroy(self)
                        dropped_items.remove(self)
                        # Pickup sound
                        try:
                            winsound.Beep(1200, 30)
                        except:
                            pass
            except:
                pass
        
        # Despawn timer
        self.life -= 1
        if self.life <= 0:
            destroy(self)
            if self in dropped_items:
                dropped_items.remove(self)

def drop_item(position, item_type):
    ItemEntity(position, item_type)

def get_held_type(slot_index):
    if 0 <= slot_index < len(hotbar_slots):
        return hotbar_slots[slot_index]['type']
    return None

class Voxel(Button):
    def __init__(self, position=(0,0,0), col=color.white):
        super().__init__(parent=scene, position=position, model='cube', origin_y=0.5, 
                         texture='white_cube', color=col, highlight_color=color.yellow)
        self.col = col
        self.breaking_start_time = None
        self.is_breaking = False
        self.is_visible = True
        # Set hardness based on block type
        if col == color.green:  # Grass
            self.hardness = 0.3
        elif col == WOOD_COLOR:  # Wood (tree trunks)
            self.hardness = 0.6
        elif col == color.brown:  # Dirt
            self.hardness = 0.4
        elif col == color.dark_gray:  # Stone
            self.hardness = 1.0
        elif col == LEAF_COLOR:  # Leaves
            self.hardness = 0.15
        else:
            self.hardness = 0.5
        all_voxels.append(self)
    
    def update_visibility(self, player_pos):
        """Update visibility based on distance from player."""
        dist = distance(self.position, player_pos)
        should_be_visible = dist <= RENDER_DISTANCE
        if should_be_visible != self.is_visible:
            self.is_visible = should_be_visible
            self.enabled = should_be_visible
    
    def input(self, key):
        # Don't allow breaking or placing if crafting UI is open
        if crafting_open:
            return
        if not self.is_visible:
            return
        if self.hovered and distance(self.world_position, camera.world_position) <= 7:
            if key == 'left mouse down':
                self.breaking_start_time = time.time()
                self.is_breaking = True
            if key == 'left mouse up':
                self.breaking_start_time = None
                self.is_breaking = False
                self.scale = 1.0
            if key == 'right mouse down':
                global selected_slot
                held = None
                if selected_slot < len(hotbar_slots):
                    held = hotbar_slots[selected_slot]['type']
                    cnt = hotbar_slots[selected_slot]['count']
                    if held and cnt > 0:
                        Voxel(position=self.position + mouse.normal, col=ITEM_COLORS.get(held, color.white))
                        hotbar_slots[selected_slot]['count'] -= 1
                        if hotbar_slots[selected_slot]['count'] <= 0:
                            hotbar_slots[selected_slot]['type'] = None
                            hotbar_slots[selected_slot]['count'] = 0
                        try:
                            winsound.Beep(880, 12)
                        except:
                            pass
    
    def update(self):
        if not self.is_visible:
            return
        if self.is_breaking and self.breaking_start_time:
            elapsed = time.time() - self.breaking_start_time
            progress = elapsed / self.hardness
            if progress >= 1.0:
                # Spawn breaking particles
                spawn_breaking_particles(self.position, self.col)
                # Drop item on ground instead of adding directly to hotbar
                if self.col == color.green:
                    drop_item(self.position, 'grass')
                elif self.col == color.dark_gray:
                    drop_item(self.position, 'stone')
                elif self.col == WOOD_COLOR:
                    drop_item(self.position, 'wood')
                elif self.col == color.brown:
                    drop_item(self.position, 'dirt')
                elif self.col == LEAF_COLOR:
                    drop_item(self.position, 'leaves')
                elif self.col == SAND_COLOR:
                    drop_item(self.position, 'sand')
                elif self.col == CACTUS_COLOR:
                    drop_item(self.position, 'cactus')
                if self in all_voxels:
                    all_voxels.remove(self)
                destroy(self)
            else:
                self.scale = 0.8 + (0.2 * (1 - progress))
        elif not self.is_breaking:
            self.scale = 1.0

def generate_tree(x, y, z):
    # Trunk
    for i in range(3):
        Voxel(position=(x, y + i, z), col=WOOD_COLOR)
    # Leaves
    for lx in range(-1, 2):
        for lz in range(-1, 2):
            Voxel(position=(x + lx, y + 3, z + lz), col=LEAF_COLOR)

def generate_cactus(x, y, z):
    # Cactus trunk
    height = random.randint(2, 4)
    for i in range(height):
        Voxel(position=(x, y + i, z), col=CACTUS_COLOR)

def get_biome(x, z):
    """Determine biome using Perlin noise for organic distribution."""
    # Use noise for biome distribution - adjusted scale for more variety
    biome_noise = pnoise([x * 0.05, z * 0.05])
    
    # Adjusted thresholds to ensure all 3 biomes appear
    if biome_noise < -0.2:
        return 'plains'
    elif biome_noise < 0.4:
        return 'mountains'
    else:
        return 'desert'

def get_biome_blend(x, z):
    """Get blending factor between biomes for smooth transitions."""
    # Sample multiple points to determine transition
    center_biome = get_biome(x, z)
    
    # Sample nearby points
    samples = [
        get_biome(x + 2, z),
        get_biome(x - 2, z),
        get_biome(x, z + 2),
        get_biome(x, z - 2),
        get_biome(x + 1, z + 1),
        get_biome(x - 1, z - 1),
    ]
    
    # Check if we're in a transition zone
    transition_count = sum(1 for s in samples if s != center_biome)
    blend_factor = transition_count / len(samples)
    
    return center_biome, blend_factor

def blend_value(val1, val2, factor):
    """Blend between two values based on factor (0-1)."""
    return val1 * (1 - factor) + val2 * factor

def generate_world():
    for z in range(WORLD_SIZE):
        for x in range(WORLD_SIZE):
            biome, blend_factor = get_biome_blend(x, z)
            noise_val = pnoise([x * 0.1, z * 0.1])
            
            # Get properties for current biome
            if biome == 'plains':
                base_height = int((noise_val + 1) * 4) + 2
                tree_chance = 0.01
                surface_block = color.green
                underground_block = color.brown
                secondary_block = color.green  # For blending
            elif biome == 'mountains':
                base_height = int((noise_val + 1) * MAX_HEIGHT * 1.5)
                tree_chance = 0.03
                surface_block = color.green
                underground_block = color.dark_gray
                secondary_block = color.brown  # For blending
            else:  # desert
                base_height = int((noise_val + 1) * 3) + 2
                tree_chance = 0
                surface_block = SAND_COLOR
                underground_block = SAND_COLOR
                secondary_block = SAND_COLOR
            
            # If in transition zone, blend with neighboring biome
            if blend_factor > 0:
                # Sample neighboring biome properties
                neighbor_biome = None
                for dx, dz in [(2, 0), (-2, 0), (0, 2), (0, -2)]:
                    nb = get_biome(x + dx, z + dz)
                    if nb != biome:
                        neighbor_biome = nb
                        break
                
                if neighbor_biome:
                    # Blend height
                    if neighbor_biome == 'plains':
                        neighbor_height = int((noise_val + 1) * 4) + 2
                    elif neighbor_biome == 'mountains':
                        neighbor_height = int((noise_val + 1) * MAX_HEIGHT * 1.5)
                    else:
                        neighbor_height = int((noise_val + 1) * 3) + 2
                    
                    height = int(blend_value(base_height, neighbor_height, blend_factor * 0.7))
                else:
                    height = base_height
            else:
                height = base_height
            
            # Generate blocks
            for y in range(height):
                if y == height - 1:
                    block_color = surface_block
                elif y > height - 4:
                    block_color = underground_block
                else:
                    block_color = color.dark_gray
                Voxel(position=(x, y, z), col=block_color)
            
            # Biome-specific features with smooth transitions
            if biome == 'plains' or biome == 'mountains':
                # Trees in plains and mountains
                if blend_factor < 0.5 and random.random() < tree_chance and height > 2:
                    generate_tree(x, height, z)
            elif biome == 'desert':
                # Cacti in desert
                if blend_factor < 0.5 and random.random() < 0.03 and height > 2:
                    generate_cactus(x, height, z)

generate_world()

# Biome display
biome_text = Text(
    parent=camera.ui,
    text='Biome: Unknown',
    position=(0.65, 0.45),
    origin=(0, 0),
    scale=2,
    color=color.white,
    z=0.5,
)

player = FirstPersonController()
player.cursor.visible = True
player.speed = 5
player.sprint_speed = 10
player.normal_speed = 5
player.is_sprinting = False

# Crosshair
crosshair_h = Entity(
    parent=camera.ui,
    model='quad',
    scale=(0.02, 0.002),
    position=(0, 0),
    color=color.white,
    z=1
)
crosshair_v = Entity(
    parent=camera.ui,
    model='quad',
    scale=(0.002, 0.02),
    position=(0, 0),
    color=color.white,
    z=1
)

# Reach indicator
reach_indicator = Text(
    parent=camera.ui,
    text='',
    position=(0, 0.15),
    origin=(0.5, 0.5),
    scale=1.2,
    color=color.red,
    z=0.5,
)

# --- Hotbar UI ---
HOTBAR_COLOR = color.rgb(0.12, 0.12, 0.12)
hotbar = Panel(
    parent=camera.ui,
    scale=(0.9, 0.12),
    position=(0, -0.42),
    color=HOTBAR_COLOR,
)

# 8 dividers for 9 slots
for i in range(1, 9):
    x_pos = -0.5 + i/9
    Entity(
        parent=hotbar,
        model='quad',
        scale=(0.015, 1.0),
        position=(x_pos, 0),
        color=color.rgb(0.2, 0.2, 0.2),
        z=-0.01
    )

# Slot centers
SLOT_SCREEN_X = [-0.5 + (i + 0.5) / 9 for i in range(9)]
HOTBAR_SCREEN_Y = -0.42

# Slot number labels (1-9) below hotbar
slot_numbers = []
for i in range(9):
    num_text = Text(
        parent=camera.ui,
        text=str(i + 1),
        position=(SLOT_SCREEN_X[i], HOTBAR_SCREEN_Y - 0.25),
        origin=(0.5, 0.5),
        scale=1.5,
        color=color.gray,
        z=0.5,
    )
    slot_numbers.append(num_text)

hotbar_slot_icons = []
for i in range(9):
    x_pos = -0.5 + (i + 0.5) / 9
    icon = Entity(
        parent=hotbar,
        model='quad',
        scale=(0.08, 0.7),
        position=(x_pos, 0),
        color=color.white,
        z=-0.02,
    )
    icon.slot_index = i
    
    count_text = Text(
        parent=camera.ui,
        text='',
        position=(SLOT_SCREEN_X[i], HOTBAR_SCREEN_Y + 0.18),
        origin=(0.5, 0.5),
        scale=1.8,
        color=color.white,
        z=0.5,
    )
    icon.count_text = count_text
    hotbar_slot_icons.append(icon)

# Holding text
holding_text = Text(
    parent=camera.ui,
    text='Holding: None',
    position=(0, HOTBAR_SCREEN_Y + 0.35),
    origin=(0.5, 0.5),
    scale=2.0,
    color=color.white,
    z=0.5,
)

# Sprint indicator
sprint_text = Text(
    parent=camera.ui,
    text='',
    position=(0.7, -0.35),
    origin=(0.5, 0.5),
    scale=1.5,
    color=color.yellow,
    z=0.5,
)

# Selection borders
selection_borders = []
for i in range(9):
    x_pos = -0.5 + (i + 0.5) / 9
    top = Entity(parent=hotbar, model='quad', scale=(0.10, 0.02), position=(x_pos, 0.35), color=color.white, z=-0.03)
    bottom = Entity(parent=hotbar, model='quad', scale=(0.10, 0.02), position=(x_pos, -0.35), color=color.white, z=-0.03)
    left = Entity(parent=hotbar, model='quad', scale=(0.02, 0.72), position=(x_pos - 0.045, 0), color=color.white, z=-0.03)
    right = Entity(parent=hotbar, model='quad', scale=(0.02, 0.72), position=(x_pos + 0.045, 0), color=color.white, z=-0.03)
    for seg in (top, bottom, left, right):
        seg.enabled = False
    selection_borders.append([top, bottom, left, right])

def update_selection_border():
    for idx, segments in enumerate(selection_borders):
        if idx < len(hotbar_slots):
            s = hotbar_slots[idx]
            has_item = (s.get('type') is not None) and (s.get('count', 0) > 0)
            enabled = (idx == selected_slot) and has_item
        else:
            enabled = False
        for seg in segments:
            seg.enabled = enabled

def update_hotbar_slots():
    for i, icon in enumerate(hotbar_slot_icons):
        if i < len(hotbar_slots):
            s = hotbar_slots[i]
            if s.get('type') is not None:
                icon.enabled = True
                icon.color = ITEM_COLORS.get(s['type'], color.white)
                count = s.get('count', 0)
                if count > 0:
                    icon.count_text.enabled = True
                    icon.count_text.text = str(count)
                else:
                    icon.count_text.enabled = False
                    icon.count_text.text = ''
            else:
                icon.enabled = False
                icon.count_text.enabled = False
                icon.count_text.text = ''
    update_selection_border()
    
    # Update holding text
    global selected_slot
    held = 'None'
    if selected_slot < len(hotbar_slots):
        t = hotbar_slots[selected_slot].get('type')
        if t:
            held = t.capitalize()
    holding_text.text = f'Holding: {held}'

# --- Crafting System ---
crafting_open = False
crafting_grid = [[None, None], [None, None]]  # 2x2 grid storing item types
crafting_entities = []  # UI entities for crafting
crafting_slot_visuals = []  # Visual representations of items in crafting slots
dragged_item = None  # Currently dragged item
dragged_item_visual = None  # Visual entity following mouse
CRAFTING_RECIPES = {
    # Format: ((item1, item2), (item3, item4)): output
    (('wood', 'wood'), ('wood', 'wood')): 'cobble',
    (('stone', None), (None, 'stone')): 'sand',
    (('dirt', 'dirt'), (None, None)): 'brick',
}

def toggle_crafting():
    global crafting_open
    crafting_open = not crafting_open
    for entity in crafting_entities:
        entity.enabled = crafting_open
    
    # Lock/unlock mouse for UI interaction
    if crafting_open:
        mouse.locked = False
        player.enabled = False  # Disable player movement while crafting
    else:
        mouse.locked = True
        player.enabled = True  # Re-enable player movement

def check_crafting_recipe():
    """Check if current grid matches a recipe and return output item."""
    grid_tuple = (
        (crafting_grid[0][0], crafting_grid[0][1]),
        (crafting_grid[1][0], crafting_grid[1][1])
    )
    return CRAFTING_RECIPES.get(grid_tuple, None)

# Crafting UI
crafting_panel = Panel(
    parent=camera.ui,
    scale=(0.4, 0.4),
    position=(0, 0),
    color=color.rgb(0.2, 0.2, 0.2),
    enabled=False
)
crafting_entities.append(crafting_panel)

# 2x2 crafting grid slots
crafting_slots = []
for row in range(2):
    for col in range(2):
        x_pos = -0.15 + col * 0.15
        y_pos = 0.15 - row * 0.15
        slot = Entity(
            parent=crafting_panel,
            model='quad',
            scale=(0.12, 0.12),
            position=(x_pos, y_pos),
            color=color.rgb(0.3, 0.3, 0.3),
            z=-0.01
        )
        crafting_entities.append(slot)
        crafting_slots.append((slot, row, col))
        
        # Add visual entity for item in this slot
        item_visual = Entity(
            parent=crafting_panel,
            model='quad',
            scale=(0.08, 0.08),
            position=(x_pos, y_pos),
            color=color.white,
            z=-0.02,
            enabled=False
        )
        crafting_slot_visuals.append(item_visual)
        crafting_entities.append(item_visual)

# Output slot
output_slot = Entity(
    parent=crafting_panel,
    model='quad',
    scale=(0.12, 0.12),
    position=(0.25, 0),
    color=color.rgb(0.4, 0.4, 0.4),
    z=-0.01
)
crafting_entities.append(output_slot)

# Crafting title
crafting_title = Text(
    parent=camera.ui,
    text='Crafting (Press C to close)',
    position=(0, 0.25),
    origin=(0.5, 0.5),
    scale=2,
    color=color.white,
    z=0.5,
    enabled=False
)
crafting_entities.append(crafting_title)

def input(key):
    global selected_slot, dragged_item, dragged_item_visual
    if key == 'f11':
        window.fullscreen = not window.fullscreen
    if key in [str(i) for i in range(1,10)]:
        selected_slot = int(key) - 1
        update_selection_border()
    if key == 'c':
        toggle_crafting()
    
    # Handle mouse clicks for crafting drag and drop
    if crafting_open:
        if key == 'left mouse down':
            # Check if clicking on hotbar slot
            mouse_pos = mouse.position
            for i, icon in enumerate(hotbar_slot_icons):
                if i < len(hotbar_slots):
                    slot_screen_x = SLOT_SCREEN_X[i]
                    slot_screen_y = HOTBAR_SCREEN_Y
                    # Check if mouse is within slot bounds (approximate)
                    if abs(mouse_pos.x - slot_screen_x) < 0.05 and abs(mouse_pos.y - slot_screen_y) < 0.06:
                        s = hotbar_slots[i]
                        if s['type'] is not None and s['count'] > 0:
                            # Start dragging
                            dragged_item = {'type': s['type'], 'from_hotbar': True, 'slot': i}
                            dragged_item_visual = Entity(
                                parent=camera.ui,
                                model='quad',
                                scale=(0.06, 0.06),
                                position=mouse_pos,
                                color=ITEM_COLORS.get(s['type'], color.white),
                                z=1
                            )
                            break
        
        elif key == 'left mouse up':
            # Drop item
            if dragged_item:
                mouse_pos = mouse.position
                # Check if dropped on crafting slot
                for idx, (slot_entity, row, col) in enumerate(crafting_slots):
                    slot_pos = slot_entity.position
                    # Convert slot position to screen coordinates (approximate)
                    slot_screen_x = slot_pos.x * 0.4  # Scale by crafting panel scale
                    slot_screen_y = slot_pos.y * 0.4
                    
                    if abs(mouse_pos.x - slot_screen_x) < 0.06 and abs(mouse_pos.y - slot_screen_y) < 0.06:
                        # Place item in crafting slot
                        if crafting_grid[row][col] is None:
                            crafting_grid[row][col] = dragged_item['type']
                            # Remove from hotbar
                            if dragged_item['from_hotbar']:
                                hotbar_slots[dragged_item['slot']]['count'] -= 1
                                if hotbar_slots[dragged_item['slot']]['count'] <= 0:
                                    hotbar_slots[dragged_item['slot']]['type'] = None
                            # Update visual
                            crafting_slot_visuals[idx].color = ITEM_COLORS.get(dragged_item['type'], color.white)
                            crafting_slot_visuals[idx].enabled = True
                            break
                
                # Clean up dragged item
                if dragged_item_visual:
                    destroy(dragged_item_visual)
                    dragged_item_visual = None
                dragged_item = None

# Frame counter for optimization
frame_count = 0
last_cull_frame = 0

def update():
    global frame_count, last_cull_frame
    frame_count += 1
    
    # Sprinting mechanics
    if held_keys['shift']:
        if not player.is_sprinting:
            player.speed = player.sprint_speed
            player.is_sprinting = True
            sprint_text.text = '>> SPRINTING <<'
    else:
        if player.is_sprinting:
            player.speed = player.normal_speed
            player.is_sprinting = False
            sprint_text.text = ''
    
    # Update visibility culling every 10 frames (performance optimization)
    if frame_count - last_cull_frame >= 10:
        last_cull_frame = frame_count
        try:
            player_pos = player.position
            # Only update visibility for a batch of blocks each frame
            batch_size = 100
            start_idx = (frame_count // 10 * batch_size) % len(all_voxels)
            end_idx = min(start_idx + batch_size, len(all_voxels))
            for voxel in all_voxels[start_idx:end_idx]:
                if voxel and not voxel.picked_up:
                    voxel.update_visibility(player_pos)
        except:
            pass
    
    # Update crosshair and reach indicator (optimized - only check visible blocks)
    try:
        hovered_block = None
        # Only check visible voxels near player
        for voxel in all_voxels:
            if voxel and voxel.is_visible and hasattr(voxel, 'hovered') and voxel.hovered:
                dist = distance(voxel.world_position, camera.world_position)
                if dist <= 7:
                    hovered_block = voxel
                    break
        
        if hovered_block:
            crosshair_h.color = color.green
            crosshair_v.color = color.green
            reach_indicator.text = ''
        else:
            crosshair_h.color = color.white
            crosshair_v.color = color.white
            reach_indicator.text = ''
    except:
        pass
    
    # Update dragged item position to follow mouse
    global dragged_item_visual
    if dragged_item_visual:
        dragged_item_visual.position = mouse.position
    
    # Update biome display
    try:
        player_x = int(player.position.x)
        player_z = int(player.position.z)
        current_biome = get_biome(player_x, player_z)
        biome_names = {
            'plains': 'Plains',
            'mountains': 'Mountains', 
            'desert': 'Desert'
        }
        biome_text.text = f'Biome: {biome_names.get(current_biome, "Unknown")}'
    except:
        pass
    
    update_hotbar_slots()

app.run()
