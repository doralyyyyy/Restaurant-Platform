#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
生成测试数据脚本
用于创建用户、餐厅、菜品和订单数据
"""

import os
import sys
import random
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import uuid
import math

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Restaurant, Category, Dish, Order, OrderItem
from werkzeug.security import generate_password_hash

# 菜品名称和分类
DISH_NAMES = {
    '饮品': [
        '冰美式咖啡', '拿铁咖啡', '卡布奇诺', '焦糖玛奇朵', '抹茶拿铁',
        '柠檬蜂蜜茶', '珍珠奶茶', '红豆奶茶', '芒果冰沙', '草莓奶昔',
        '鲜榨橙汁', '西瓜汁', '柠檬水', '蜂蜜柚子茶', '乌龙茶'
    ],
    '菜品': [
        '宫保鸡丁', '麻婆豆腐', '鱼香肉丝', '糖醋里脊', '红烧肉',
        '回锅肉', '水煮鱼', '酸菜鱼', '辣子鸡', '口水鸡',
        '蒜蓉西兰花', '干煸四季豆', '地三鲜', '鱼香茄子', '蚂蚁上树'
    ],
    '主食': [
        '扬州炒饭', '蛋炒饭', '牛肉炒饭', '海鲜炒饭', '咖喱炒饭',
        '担担面', '牛肉面', '炸酱面', '热干面', '刀削面',
        '小笼包', '生煎包', '蒸饺', '水饺', '馄饨'
    ],
    '小吃': [
        '炸鸡翅', '炸鸡腿', '薯条', '洋葱圈', '鸡米花',
        '春卷', '煎饺', '锅贴', '烧卖', '虾饺',
        '蛋挞', '红豆派', '香芋派', '鸡块', '鸡排'
    ]
}

# 用户名称
USERNAMES = [
    '张三', '李四', '王五', '赵六', '钱七',
    '孙八', '周九', '吴十', '郑十一', '王十二',
    '刘十三', '陈十四', '杨十五'
]

# 餐厅名称
RESTAURANT_NAMES = [
    '美味餐厅', '香满楼', '食尚坊', '好味道', '美食天地',
    '香香餐厅', '味蕾餐厅', '美食汇', '食客之家', '美味轩',
    '香格里拉', '美食城', '食尚汇'
]

# 菜品描述模板
DESCRIPTIONS = [
    '精选优质食材，精心烹制，口感鲜美',
    '传统工艺制作，味道正宗，营养丰富',
    '新鲜食材，现做现卖，健康美味',
    '招牌菜品，深受顾客喜爱',
    '经典口味，回味无穷',
    '特色菜品，值得一试',
    '营养搭配，色香味俱全'
]


def ensure_upload_dirs():
    """确保上传目录存在"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for sub in ['avatars', 'logos', 'dishes']:
        path = os.path.join(base_dir, 'static', 'uploads', sub)
        os.makedirs(path, exist_ok=True)


def generate_avatar_image(width, height, text, save_path):
    """生成真实的头像图片（圆形、渐变背景、图案）"""
    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # 生成渐变背景色（温暖的颜色）
    colors = [
        [(135, 206, 250), (255, 182, 193)],  # 天蓝到粉红
        [(255, 218, 185), (255, 239, 213)],  # 桃色到杏仁
        [(230, 230, 250), (255, 228, 225)],  # 薰衣草到淡粉
        [(176, 196, 222), (255, 250, 205)],  # 淡蓝到淡黄
        [(255, 192, 203), (255, 228, 225)],  # 粉红到淡粉
        [(144, 238, 144), (152, 251, 152)],  # 淡绿到淡绿
        [(255, 218, 185), (255, 160, 122)],  # 桃色到鲑鱼色
        [(221, 160, 221), (238, 130, 238)],  # 淡紫到紫色
        [(255, 239, 213), (255, 218, 185)],  # 杏仁到桃色
        [(175, 238, 238), (144, 238, 144)],  # 淡青到淡绿
    ]
    color_pair = random.choice(colors)
    start_color = color_pair[0]
    end_color = color_pair[1]
    
    # 绘制径向渐变（从中心向外）
    center_x, center_y = width // 2, height // 2
    max_radius = int(math.sqrt(center_x**2 + center_y**2))
    
    for radius in range(max_radius, -1, -1):
        ratio = radius / max_radius
        r = int(start_color[0] * (1 - ratio) + end_color[0] * ratio)
        g = int(start_color[1] * (1 - ratio) + end_color[1] * ratio)
        b = int(start_color[2] * (1 - ratio) + end_color[2] * ratio)
        draw.ellipse([center_x - radius, center_y - radius, 
                     center_x + radius, center_y + radius], 
                    fill=(r, g, b))
    
    # 添加装饰性图案（圆形或花纹）
    pattern_type = random.choice(['circles', 'dots', 'lines', 'waves'])
    if pattern_type == 'circles':
        # 绘制几个半透明圆圈（混合颜色实现半透明效果）
        for _ in range(random.randint(2, 4)):
            x = random.randint(0, width)
            y = random.randint(0, height)
            r = random.randint(10, 30)
            # 使用更浅的白色实现半透明效果
            white_alpha = random.randint(180, 220)
            draw.ellipse([x - r, y - r, x + r, y + r], 
                        fill=(white_alpha, white_alpha, white_alpha), 
                        outline=(white_alpha, white_alpha, white_alpha))
    elif pattern_type == 'dots':
        # 绘制小点
        for _ in range(random.randint(10, 20)):
            x = random.randint(0, width)
            y = random.randint(0, height)
            dot_color = random.randint(200, 255)
            draw.ellipse([x - 2, y - 2, x + 2, y + 2], 
                        fill=(dot_color, dot_color, dot_color))
    
    # 添加文字（用户名首字母）
    try:
        font_path = 'C:/Windows/Fonts/msyh.ttc'
        if not os.path.exists(font_path):
            font_path = 'C:/Windows/Fonts/simhei.ttf'
        if os.path.exists(font_path):
            font_size = int(min(width, height) * 0.5)
            font = ImageFont.truetype(font_path, font_size)
        else:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # 计算文字位置并绘制
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2 - 5
    
    # 绘制文字阴影
    shadow_offset = 2
    draw.text((x + shadow_offset, y + shadow_offset), text, 
              fill=(100, 100, 100), font=font)
    draw.text((x, y), text, fill=(255, 255, 255), font=font)
    
    # 应用轻微模糊使图片更柔和
    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
    
    img.save(save_path, quality=95)
    return save_path


def generate_logo_image(width, height, text, save_path):
    """生成真实的Logo图片（设计感、图案）"""
    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # 选择Logo风格颜色（更专业、更有设计感）
    logo_colors = [
        [(70, 130, 180), (255, 255, 255)],  # 钢蓝色配白色
        [(255, 69, 0), (255, 255, 255)],    # 橙红色配白色
        [(50, 205, 50), (255, 255, 255)],   # 绿色配白色
        [(138, 43, 226), (255, 255, 255)],  # 紫色配白色
        [(255, 20, 147), (255, 255, 255)],  # 深粉红配白色
        [(0, 191, 255), (255, 255, 255)],   # 深天蓝配白色
        [(255, 140, 0), (255, 255, 255)],   # 深橙色配白色
        [(34, 139, 34), (255, 255, 255)],   # 森林绿配白色
    ]
    bg_color, text_color = random.choice(logo_colors)
    
    # 绘制渐变背景（线性渐变）
    for y in range(height):
        ratio = y / height
        r = int(bg_color[0] * (1 - ratio) + min(255, bg_color[0] + 30) * ratio)
        g = int(bg_color[1] * (1 - ratio) + min(255, bg_color[1] + 30) * ratio)
        b = int(bg_color[2] * (1 - ratio) + min(255, bg_color[2] + 30) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # 添加几何图案装饰
    pattern_style = random.choice(['diagonal', 'grid', 'circles', 'waves'])
    
    if pattern_style == 'diagonal':
        # 斜线图案
        for i in range(0, width + height, 20):
            alpha = 30
            color = tuple(min(255, c + alpha) for c in bg_color)
            draw.line([(i, 0), (i - height, height)], fill=color, width=2)
    
    elif pattern_style == 'grid':
        # 网格图案
        for x in range(0, width, 40):
            alpha = 40
            color = tuple(min(255, c + alpha) for c in bg_color)
            draw.line([(x, 0), (x, height)], fill=color, width=1)
        for y in range(0, height, 40):
            alpha = 40
            color = tuple(min(255, c + alpha) for c in bg_color)
            draw.line([(0, y), (width, y)], fill=color, width=1)
    
    elif pattern_style == 'circles':
        # 圆形装饰
        for _ in range(random.randint(3, 6)):
            x = random.randint(0, width)
            y = random.randint(0, height)
            r = random.randint(20, 60)
            alpha = 50
            color = tuple(min(255, c + alpha) for c in bg_color)
            draw.ellipse([x - r, y - r, x + r, y + r], 
                        outline=color, width=2)
    
    # 绘制中心装饰框或圆形
    center_x, center_y = width // 2, height // 2
    decor_size = min(width, height) * 0.6
    
    if random.choice([True, False]):
        # 圆形框
        draw.ellipse([center_x - decor_size//2, center_y - decor_size//2,
                     center_x + decor_size//2, center_y + decor_size//2],
                    outline=text_color, width=4)
    else:
        # 方形框，带圆角效果
        margin = decor_size // 2
        points = [
            (center_x - margin + 10, center_y - margin),
            (center_x + margin - 10, center_y - margin),
            (center_x + margin, center_y - margin + 10),
            (center_x + margin, center_y + margin - 10),
            (center_x + margin - 10, center_y + margin),
            (center_x - margin + 10, center_y + margin),
            (center_x - margin, center_y + margin - 10),
            (center_x - margin, center_y - margin + 10),
        ]
        for i in range(len(points)):
            draw.line([points[i], points[(i+1)%len(points)]], 
                     fill=text_color, width=4)
    
    # 添加文字
    try:
        font_path = 'C:/Windows/Fonts/msyh.ttc'
        if not os.path.exists(font_path):
            font_path = 'C:/Windows/Fonts/simhei.ttf'
        if os.path.exists(font_path):
            font_size = int(min(width, height) * 0.3)
            font = ImageFont.truetype(font_path, font_size)
        else:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    # 绘制文字阴影使文字更突出
    shadow_offset = 2
    draw.text((x + shadow_offset, y + shadow_offset), text, 
              fill=(50, 50, 50), font=font)
    draw.text((x, y), text, fill=text_color, font=font)
    
    img.save(save_path, quality=95)
    return save_path


def generate_dish_image(width, height, dish_name, save_path):
    """生成真实的菜品图片（食物纹理、颜色）"""
    img = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    # 根据菜品名称选择食物色调
    food_colors = {
        '饮品': [(255, 182, 193), (255, 218, 185), (255, 250, 205), 
                (230, 230, 250), (176, 224, 230)],
        '菜品': [(255, 218, 185), (255, 228, 181), (255, 239, 213),
                (255, 222, 173), (250, 235, 215)],
        '主食': [(255, 248, 220), (255, 239, 213), (255, 228, 196),
                (245, 245, 220), (255, 250, 240)],
        '小吃': [(255, 218, 185), (255, 228, 181), (255, 239, 213),
                (255, 222, 173), (250, 235, 215)],
    }
    
    # 判断菜品类型
    dish_type = '菜品'
    for category, names in DISH_NAMES.items():
        if dish_name in names:
            dish_type = category
            break
    
    base_colors = food_colors.get(dish_type, food_colors['菜品'])
    base_color = random.choice(base_colors)
    
    # 创建食物般的纹理背景（多层次的渐变和斑点）
    # 第一层：主色调渐变
    for y in range(height):
        ratio = y / height
        variation = random.randint(-20, 20)
        r = min(255, max(0, base_color[0] + int(variation * ratio)))
        g = min(255, max(0, base_color[1] + int(variation * ratio)))
        b = min(255, max(0, base_color[2] + int(variation * ratio)))
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # 第二层：添加纹理斑点（模拟食物的质感）
    for _ in range(random.randint(50, 100)):
        x = random.randint(0, width)
        y = random.randint(0, height)
        size = random.randint(5, 30)
        
        # 随机选择比背景稍深或稍浅的颜色
        variation = random.choice([-40, -20, 20, 40])
        r = min(255, max(0, base_color[0] + variation))
        g = min(255, max(0, base_color[1] + variation))
        b = min(255, max(0, base_color[2] + variation))
        
        draw.ellipse([x - size, y - size, x + size, y + size], 
                    fill=(r, g, b))
    
    # 第三层：添加高光和阴影（增加立体感）
    # 高光
    highlight_x = random.randint(width // 4, width * 3 // 4)
    highlight_y = random.randint(height // 4, height // 3)
    highlight_size = random.randint(100, 200)
    for i in range(highlight_size, 0, -8):
        # 高光效果：逐渐变亮
        brightness = 50 - int(i / highlight_size * 40)
        r = min(255, base_color[0] + brightness)
        g = min(255, base_color[1] + brightness)
        b = min(255, base_color[2] + brightness)
        draw.ellipse([highlight_x - i, highlight_y - i, 
                     highlight_x + i, highlight_y + i],
                    outline=(r, g, b), width=2)
    
    # 阴影
    shadow_x = random.randint(width // 4, width * 3 // 4)
    shadow_y = random.randint(height * 2 // 3, height * 3 // 4)
    shadow_size = random.randint(80, 150)
    for i in range(shadow_size, 0, -8):
        # 阴影效果：逐渐变暗
        darkness = 30
        r = max(0, base_color[0] - darkness)
        g = max(0, base_color[1] - darkness)
        b = max(0, base_color[2] - darkness)
        draw.ellipse([shadow_x - i, shadow_y - i, 
                     shadow_x + i, shadow_y + i],
                    outline=(r, g, b), width=2)
    
    # 添加装饰性元素（模拟食物的点缀）
    if random.random() > 0.3:  # 70%的概率添加装饰
        for _ in range(random.randint(5, 15)):
            x = random.randint(0, width)
            y = random.randint(0, height)
            size = random.randint(3, 8)
            # 使用对比色
            accent_color = (
                min(255, base_color[0] + random.randint(-50, 50)),
                min(255, base_color[1] + random.randint(-50, 50)),
                min(255, base_color[2] + random.randint(-50, 50))
            )
            draw.ellipse([x - size, y - size, x + size, y + size], 
                        fill=accent_color)
    
    # 添加菜品名称文字（可选，较小的字体）
    if random.random() > 0.5:  # 50%的概率显示文字
        try:
            font_path = 'C:/Windows/Fonts/msyh.ttc'
            if not os.path.exists(font_path):
                font_path = 'C:/Windows/Fonts/simhei.ttf'
            if os.path.exists(font_path):
                font_size = int(min(width, height) * 0.08)
                font = ImageFont.truetype(font_path, font_size)
            else:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        text_color = (80, 80, 80) if sum(base_color) > 400 else (220, 220, 220)
        bbox = draw.textbbox((0, 0), dish_name, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) // 2
        y = height - text_height - 20
        
        # 绘制半透明背景使文字更清晰（使用浅灰色模拟半透明效果）
        padding = 10
        draw.rectangle([x - padding, y - padding, 
                       x + text_width + padding, y + text_height + padding],
                      fill=(240, 240, 240))
        draw.text((x, y), dish_name, fill=text_color, font=font)
    
    # 应用轻微模糊和锐化，模拟照片效果
    img = img.filter(ImageFilter.GaussianBlur(radius=0.3))
    
    img.save(save_path, quality=95)
    return save_path


def create_test_users():
    """创建测试用户"""
    print("创建测试用户...")
    users = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    for i, username in enumerate(USERNAMES[:10]):
        # 检查用户是否已存在
        if User.query.filter_by(username=username).first():
            print(f"  用户 {username} 已存在，跳过")
            user = User.query.filter_by(username=username).first()
            users.append(user)
            continue
        
        # 生成头像
        avatar_path = os.path.join(base_dir, 'static', 'uploads', 'avatars', f'{uuid.uuid4().hex}.jpg')
        generate_avatar_image(100, 100, username[0], avatar_path)
        rel_avatar = os.path.join('uploads', 'avatars', os.path.basename(avatar_path)).replace('\\', '/')
        
        user = User(
            username=username,
            email=None,
            password_hash=generate_password_hash('123456'),  # 统一密码
            avatar=rel_avatar
        )
        db.session.add(user)
        users.append(user)
        print(f"  创建用户: {username}")
    
    db.session.commit()
    print(f"[OK] 创建了 {len(users)} 个用户\n")
    return users


def create_test_restaurants(users):
    """创建测试餐厅"""
    print("创建测试餐厅...")
    restaurants = []
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 为前10个用户创建餐厅
    for i, user in enumerate(users[:10]):
        if user.restaurant:
            print(f"  用户 {user.username} 已有餐厅，跳过")
            restaurants.append(user.restaurant)
            continue
        
        restaurant_name = RESTAURANT_NAMES[i] if i < len(RESTAURANT_NAMES) else f'餐厅{i+1}'
        
        # 检查餐厅名是否已存在
        if Restaurant.query.filter_by(name=restaurant_name).first():
            restaurant_name = f'{restaurant_name}_{i}'
        
        # 生成logo
        logo_path = os.path.join(base_dir, 'static', 'uploads', 'logos', f'{uuid.uuid4().hex}.jpg')
        generate_logo_image(300, 300, restaurant_name[:2], logo_path)
        rel_logo = os.path.join('uploads', 'logos', os.path.basename(logo_path)).replace('\\', '/')
        
        restaurant = Restaurant(
            name=restaurant_name,
            logo=rel_logo,
            owner_id=user.id
        )
        db.session.add(restaurant)
        db.session.flush()  # 获取ID
        
        # 创建默认分类
        for cat_name in ['饮品', '菜品', '主食', '小吃']:
            category = Category(name=cat_name, restaurant_id=restaurant.id)
            db.session.add(category)
        
        restaurants.append(restaurant)
        print(f"  创建餐厅: {restaurant_name} (所有者: {user.username})")
    
    db.session.commit()
    print(f"[OK] 创建了 {len(restaurants)} 个餐厅\n")
    return restaurants


def create_test_dishes(restaurants):
    """创建测试菜品"""
    print("创建测试菜品...")
    total_dishes = 0
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    for restaurant in restaurants:
        categories = Category.query.filter_by(restaurant_id=restaurant.id).all()
        cat_map = {cat.name: cat for cat in categories}
        
        dishes_count = 0
        for cat_name, dish_names in DISH_NAMES.items():
            if cat_name not in cat_map:
                continue
            
            category = cat_map[cat_name]
            # 每个分类创建5-8个菜品
            selected_dishes = random.sample(dish_names, min(random.randint(5, 8), len(dish_names)))
            
            for dish_name in selected_dishes:
                # 检查菜品是否已存在
                if Dish.query.filter_by(name=dish_name, restaurant_id=restaurant.id).first():
                    continue
                
                # 生成价格（根据分类不同价格范围）
                if cat_name == '饮品':
                    price = Decimal(str(random.uniform(8, 25)))
                elif cat_name == '菜品':
                    price = Decimal(str(random.uniform(25, 68)))
                elif cat_name == '主食':
                    price = Decimal(str(random.uniform(15, 35)))
                else:  # 小吃
                    price = Decimal(str(random.uniform(10, 30)))
                
                price = round(price, 2)
                
                # 生成菜品图片
                base_name = uuid.uuid4().hex
                big_path = os.path.join(base_dir, 'static', 'uploads', 'dishes', f'{base_name}_big.jpg')
                thumb_path = os.path.join(base_dir, 'static', 'uploads', 'dishes', f'{base_name}_thumb.jpg')
                
                # 大图
                generate_dish_image(800, 600, dish_name, big_path)
                # 缩略图（先生成大图，然后缩小）
                temp_img = Image.open(big_path)
                temp_img.thumbnail((100, 100), Image.Resampling.LANCZOS)
                temp_img.save(thumb_path, quality=95)
                
                rel_big = os.path.join('uploads', 'dishes', os.path.basename(big_path)).replace('\\', '/')
                rel_thumb = os.path.join('uploads', 'dishes', os.path.basename(thumb_path)).replace('\\', '/')
                
                dish = Dish(
                    name=dish_name,
                    description=random.choice(DESCRIPTIONS),
                    price=price,
                    image=rel_big,
                    thumb=rel_thumb,
                    restaurant_id=restaurant.id,
                    category_id=category.id
                )
                db.session.add(dish)
                dishes_count += 1
                total_dishes += 1
        
        print(f"  餐厅 {restaurant.name}: 创建了 {dishes_count} 个菜品")
    
    db.session.commit()
    print(f"[OK] 总共创建了 {total_dishes} 个菜品\n")
    return total_dishes


def create_test_orders(users, restaurants):
    """创建测试订单"""
    print("创建测试订单...")
    total_orders = 0
    
    # 为每个用户创建一些订单
    for user in users:
        # 每个用户创建3-8个订单
        num_orders = random.randint(3, 8)
        
        for _ in range(num_orders):
            # 随机选择一个餐厅
            restaurant = random.choice(restaurants)
            
            # 获取该餐厅的菜品
            dishes = Dish.query.filter_by(restaurant_id=restaurant.id).all()
            if not dishes:
                continue
            
            # 每个订单包含2-5个菜品
            selected_dishes = random.sample(dishes, min(random.randint(2, 5), len(dishes)))
            
            # 计算总金额
            total_amount = Decimal('0.00')
            order_items_data = []
            
            for dish in selected_dishes:
                quantity = random.randint(1, 3)
                line_total = dish.price * quantity
                total_amount += line_total
                order_items_data.append({
                    'dish': dish,
                    'quantity': quantity,
                    'unit_price': dish.price
                })
            
            # 创建订单（随机时间，最近30天内）
            days_ago = random.randint(0, 30)
            order_time = datetime.now(timezone.utc) - timedelta(days=days_ago, hours=random.randint(0, 23))
            
            order = Order(
                customer_id=user.id,
                restaurant_id=restaurant.id,
                total_amount=total_amount,
                created_at=order_time
            )
            db.session.add(order)
            db.session.flush()  # 获取订单ID
            
            # 创建订单项
            for item_data in order_items_data:
                order_item = OrderItem(
                    order_id=order.id,
                    dish_id=item_data['dish'].id,
                    quantity=item_data['quantity'],
                    unit_price=item_data['unit_price']
                )
                db.session.add(order_item)
            
            total_orders += 1
    
    db.session.commit()
    print(f"[OK] 创建了 {total_orders} 个订单\n")
    return total_orders


def main():
    """主函数"""
    print("=" * 50)
    print("开始生成测试数据...")
    print("=" * 50)
    print()
    
    ensure_upload_dirs()
    
    with app.app_context():
        # 创建数据库表
        print("创建数据库表...")
        db.create_all()
        print("[OK] 数据库表创建完成\n")
        # 创建用户
        users = create_test_users()
        
        # 创建餐厅
        restaurants = create_test_restaurants(users)
        
        # 创建菜品
        dishes_count = create_test_dishes(restaurants)
        
        # 创建订单
        orders_count = create_test_orders(users, restaurants)
        
        print("=" * 50)
        print("测试数据生成完成！")
        print("=" * 50)
        print(f"用户数量: {len(users)}")
        print(f"餐厅数量: {len(restaurants)}")
        print(f"菜品数量: {dishes_count}")
        print(f"订单数量: {orders_count}")
        print()
        print("所有用户密码统一为: 123456")
        print("=" * 50)


if __name__ == '__main__':
    main()

