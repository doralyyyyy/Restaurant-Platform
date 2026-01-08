
import os
import uuid
import colorsys
from decimal import Decimal
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, send_from_directory
)
import re
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user, UserMixin
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import requests
from sqlalchemy import func

# ----------------- 基础配置 -----------------

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-me')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'sqlite:///' + os.path.join(BASE_DIR, 'restaurant_platform.db')
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_ROOT = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, UPLOAD_ROOT)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

# GPT 配置
GPT_BASE_URL = os.getenv('GPT_BASE_URL', 'https://aizex.top/v1')
GPT_API_KEY = os.getenv('GPT_API_KEY', 'sk-YZybkMjhj6XN6PT0iCFueG4cp0KuzXCJWRR5RnXuZuODU8hA')
GPT_MODEL = os.getenv('GPT_MODEL', 'gpt-5')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# ----------------- 自定义模板过滤器 -----------------

def format_ai_answer(text):
    """格式化AI回答，处理换行、HTML标签和Markdown格式"""
    if not text:
        return ''
    text = str(text)
    # 先移除文本中可能存在的 <br> 标签（作为纯文本），转换为换行符
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    
    # 处理markdown分隔线 --- 或 ***（必须在其他处理之前）
    text = re.sub(r'^---+$', '<hr>', text, flags=re.MULTILINE)
    text = re.sub(r'^\*{3,}$', '<hr>', text, flags=re.MULTILINE)
    
    # 处理markdown标题 # ## ### 等（必须在转义HTML之前）
    text = re.sub(r'^#### (.+?)$', r'<h6>\1</h6>', text, flags=re.MULTILINE)
    text = re.sub(r'^### (.+?)$', r'<h5>\1</h5>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+?)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+?)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    
    # 处理markdown无序列表 - 或 *（必须在转义HTML之前）
    # 先处理多级列表，按行处理
    lines = text.split('\n')
    in_list = False
    result_lines = []
    for line in lines:
        # 检查是否是列表项
        list_match = re.match(r'^(\s*)[-*]\s+(.+)$', line)
        if list_match:
            indent = len(list_match.group(1))
            content = list_match.group(2)
            if not in_list:
                result_lines.append('<ul>')
                in_list = True
            result_lines.append(f'<li>{content}</li>')
        else:
            if in_list:
                result_lines.append('</ul>')
                in_list = False
            result_lines.append(line)
    if in_list:
        result_lines.append('</ul>')
    text = '\n'.join(result_lines)
    
    # 处理中文序号（一、二、三、四等）- 作为标题处理，不是列表
    # 将"一、xxx"格式转换为标题格式
    chinese_numbers = {
        '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
        '六': '6', '七': '7', '八': '8', '九': '9', '十': '10',
        '十一': '11', '十二': '12', '十三': '13', '十四': '14', '十五': '15'
    }
    
    def convert_chinese_title(match):
        chinese = match.group(1)
        content = match.group(2)
        return f'<h4>{content}</h4>'
    
    # 将"一、xxx"格式转换为标题（不作为列表项）
    text = re.sub(r'^(\s*)([一二三四五六七八九十]+)[、.]\s+(.+)$', convert_chinese_title, text, flags=re.MULTILINE)
    
    # 处理markdown有序列表 1. 2. 等
    # 只处理连续的数字序号列表，确保是真正的列表项
    lines = text.split('\n')
    in_ordered_list = False
    result_lines = []
    last_list_number = 0
    
    for i, line in enumerate(lines):
        # 检查是否是有序列表项（数字开头）
        ordered_match = re.match(r'^(\s*)(\d+)\.\s+(.+)$', line)
        is_empty = not line.strip()
        
        if ordered_match:
            indent = len(ordered_match.group(1))
            list_number = int(ordered_match.group(2))
            content = ordered_match.group(3)
            
            # 判断是否是连续列表项（允许从1开始，或者比上一个数字大1）
            is_continuous = (not in_ordered_list and list_number == 1) or \
                          (in_ordered_list and list_number == last_list_number + 1)
            
            # 如果缩进为0且数字连续，才认为是列表项
            if indent == 0 and is_continuous:
                if not in_ordered_list:
                    result_lines.append('<ol>')
                    in_ordered_list = True
                result_lines.append(f'<li>{content}</li>')
                last_list_number = list_number
            else:
                # 不是连续列表项，关闭之前的列表（如果有）
                if in_ordered_list:
                    result_lines.append('</ol>')
                    in_ordered_list = False
                    last_list_number = 0
                result_lines.append(line)
        else:
            # 如果当前在列表中，需要判断是否关闭列表
            if in_ordered_list:
                # 检查下一行是否是连续列表项（允许中间有一个空行）
                next_is_list = False
                next_list_num = 0
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_match = re.match(r'^(\s*)(\d+)\.\s+', next_line)
                    if next_match and len(next_match.group(1)) == 0:
                        next_list_num = int(next_match.group(2))
                        next_is_list = (next_list_num == last_list_number + 1)
                
                # 如果当前是空行，但下一行是连续列表项，则保留空行但继续列表
                if is_empty and next_is_list:
                    result_lines.append('')
                else:
                    # 关闭列表
                    result_lines.append('</ol>')
                    in_ordered_list = False
                    last_list_number = 0
                    if not is_empty:
                        result_lines.append(line)
            else:
                result_lines.append(line)
    
    if in_ordered_list:
        result_lines.append('</ol>')
    text = '\n'.join(result_lines)
    
    # 处理markdown格式的粗体 **text**（必须在转义HTML之前）
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # 处理markdown格式的斜体 *text*（但避免与粗体冲突）
    text = re.sub(r'(?<!\*)\*(?![*<])([^*<]+?)(?<![*<])\*(?!\*)', r'<em>\1</em>', text)
    
    # 转义所有HTML标签（除了我们已经添加的标签）
    # 先转义 & 符号（必须在其他转义之前，但要避免重复转义）
    text = text.replace('&amp;', '___AMP___')  # 保护已转义的&
    text = text.replace('&', '&amp;')
    text = text.replace('___AMP___', '&amp;')
    
    # 转义 < 和 >，但保留我们需要的标签
    # 先保护我们需要的标签
    protected_tags = [
        ('<hr>', '___HR___'),
        ('<h3>', '___H3_START___'), ('</h3>', '___H3_END___'),
        ('<h4>', '___H4_START___'), ('</h4>', '___H4_END___'),
        ('<h5>', '___H5_START___'), ('</h5>', '___H5_END___'),
        ('<h6>', '___H6_START___'), ('</h6>', '___H6_END___'),
        ('<ul>', '___UL_START___'), ('</ul>', '___UL_END___'),
        ('<ol>', '___OL_START___'), ('</ol>', '___OL_END___'),
        ('<li>', '___LI_START___'), ('</li>', '___LI_END___'),
        ('<strong>', '___STRONG_START___'), ('</strong>', '___STRONG_END___'),
        ('<em>', '___EM_START___'), ('</em>', '___EM_END___'),
    ]
    
    for original, placeholder in protected_tags:
        text = text.replace(original, placeholder)
    
    # 转义所有剩余的 < 和 >
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    
    # 恢复我们需要的标签
    for original, placeholder in protected_tags:
        text = text.replace(placeholder, original)
    
    # 将换行符转换为 <br>，但保留块级元素之间的换行
    # 先标记块级元素
    text = text.replace('<hr>', '<hr>\n')
    text = text.replace('</h3>', '</h3>\n')
    text = text.replace('</h4>', '</h4>\n')
    text = text.replace('</h5>', '</h5>\n')
    text = text.replace('</h6>', '</h6>\n')
    text = text.replace('</ul>', '</ul>\n')
    text = text.replace('</ol>', '</ol>\n')
    
    # 将换行符转换为 <br>，但跳过空行（在块级元素之间）
    lines = text.split('\n')
    result_lines = []
    prev_was_block = False
    for line in lines:
        stripped = line.strip()
        is_block = stripped.startswith(('<hr>', '<h3>', '<h4>', '<h5>', '<h6>', '<ul>', '<ol>', '</ul>', '</ol>'))
        if not stripped:
            if not prev_was_block:
                result_lines.append('<br>')
        elif is_block:
            result_lines.append(line)
            prev_was_block = True
        else:
            result_lines.append(line + '<br>')
            prev_was_block = False
    
    text = '\n'.join(result_lines)
    # 清理多余的 <br> 标签（在块级元素前后）
    text = re.sub(r'<br>\s*(<hr>|<h[3-6]>|<ul>|<ol>)', r'\1', text)
    text = re.sub(r'(</h[3-6]>|</ul>|</ol>)\s*<br>', r'\1', text)
    
    return text


@app.template_filter('format_ai')
def format_ai_filter(text):
    """Jinja2过滤器：格式化AI回答"""
    return format_ai_answer(text)


# ----------------- 数据模型 -----------------

blacklist_table = db.Table(
    'blacklist',
    db.Column('restaurant_id', db.Integer, db.ForeignKey('restaurant.id'), primary_key=True),
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True)
)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(128), nullable=False)
    avatar = db.Column(db.String(255))  # 相对 static 路径
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 一个用户最多拥有一家餐厅
    restaurant = db.relationship('Restaurant', backref='owner', uselist=False)
    orders = db.relationship('Order', backref='customer', lazy=True)

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Restaurant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    logo = db.Column(db.String(255))  # 相对 static 路径
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    categories = db.relationship('Category', backref='restaurant', lazy=True, cascade='all, delete-orphan')
    dishes = db.relationship('Dish', backref='restaurant', lazy=True, cascade='all, delete-orphan')
    orders = db.relationship('Order', backref='restaurant', lazy=True, cascade='all, delete-orphan')

    blacklisted_users = db.relationship(
        'User',
        secondary=blacklist_table,
        backref=db.backref('blacklisted_restaurants', lazy='dynamic')
    )


class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    dishes = db.relationship('Dish', backref='category', lazy=True)


class Dish(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    image = db.Column(db.String(255))   # 大图
    thumb = db.Column(db.String(255))   # 缩略图 <= 100*100
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    order_items = db.relationship('OrderItem', backref='dish', lazy=True)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    restaurant_id = db.Column(db.Integer, db.ForeignKey('restaurant.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Numeric(10, 2), nullable=False)

    items = db.relationship('OrderItem', backref='order', lazy=True, cascade='all, delete-orphan')


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    dish_id = db.Column(db.Integer, db.ForeignKey('dish.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)


# ----------------- 登录管理 -----------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ----------------- 工具函数 -----------------

ALLOWED_IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.gif'}


def ensure_upload_dirs():
    for sub in ['avatars', 'logos', 'dishes']:
        path = os.path.join(app.config['UPLOAD_FOLDER'], sub)
        os.makedirs(path, exist_ok=True)


def save_avatar(file_storage):
    """保存用户头像，强制缩放到 100x100 以内"""
    if not file_storage:
        return None
    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise ValueError('头像格式不支持，只能上传 jpg/jpeg/png/gif')

    ensure_upload_dirs()
    avatar_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars')

    new_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(avatar_dir, new_name)

    img = Image.open(file_storage)
    img = img.convert('RGB')
    img.thumbnail((100, 100))
    img.save(save_path)

    # 返回相对 static 的路径
    rel_path = os.path.join('uploads', 'avatars', new_name)
    return rel_path.replace('\\', '/')


def save_logo(file_storage):
    """保存餐厅 logo（稍微大一点即可）"""
    if not file_storage:
        return None
    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise ValueError('Logo 格式不支持，只能上传 jpg/jpeg/png/gif')

    ensure_upload_dirs()
    logo_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'logos')

    new_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(logo_dir, new_name)

    img = Image.open(file_storage)
    img = img.convert('RGB')
    
    # 将图片裁剪为正方形（以较短边为准）
    width, height = img.size
    size = min(width, height)
    left = (width - size) // 2
    top = (height - size) // 2
    right = left + size
    bottom = top + size
    img = img.crop((left, top, right, bottom))
    
    # 调整到 300x300 正方形
    img = img.resize((300, 300), Image.Resampling.LANCZOS)
    img.save(save_path)

    rel_path = os.path.join('uploads', 'logos', new_name)
    return rel_path.replace('\\', '/')


def save_dish_images(file_storage):
    """保存菜品图片，返回 (大图路径, 缩略图路径)"""
    if not file_storage:
        return None, None
    filename = secure_filename(file_storage.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        raise ValueError('菜品图片格式不支持，只能上传 jpg/jpeg/png/gif')

    ensure_upload_dirs()
    dish_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'dishes')

    base_name = uuid.uuid4().hex

    # 大图
    big_name = f"{base_name}_big{ext}"
    big_path = os.path.join(dish_dir, big_name)

    # 缩略图
    thumb_name = f"{base_name}_thumb{ext}"
    thumb_path = os.path.join(dish_dir, thumb_name)

    img = Image.open(file_storage)
    img = img.convert('RGB')

    big_img = img.copy()
    big_img.thumbnail((800, 800))
    big_img.save(big_path)

    thumb_img = img.copy()
    thumb_img.thumbnail((100, 100))
    thumb_img.save(thumb_path)

    rel_big = os.path.join('uploads', 'dishes', big_name).replace('\\', '/')
    rel_thumb = os.path.join('uploads', 'dishes', thumb_name).replace('\\', '/')
    return rel_big, rel_thumb


def get_cart():
    """返回 session 中的购物车结构"""
    return session.get('cart', {})


def save_cart(cart):
    session['cart'] = cart
    session.modified = True


def add_to_cart(dish_id, quantity=1):
    dish = Dish.query.get_or_404(dish_id)
    restaurant_id = str(dish.restaurant_id)

    cart = get_cart()
    if restaurant_id not in cart:
        cart[restaurant_id] = {}
    dish_key = str(dish_id)
    cart[restaurant_id][dish_key] = cart[restaurant_id].get(dish_key, 0) + quantity
    # 不再删除数量为0的菜品，保留在购物车中
    save_cart(cart)


def get_cart_items_for_restaurant(restaurant_id, include_zero=False):
    """返回某餐厅在购物车中的详细条目列表和总价
    include_zero: 如果为True，包含数量为0的菜品；如果为False，只返回数量>0的菜品（用于结账）
    """
    rid = str(restaurant_id)
    cart = get_cart()
    items = cart.get(rid, {})
    if not items:
        return [], Decimal('0.00')

    dish_ids = [int(did) for did in items.keys()]
    dishes = Dish.query.filter(Dish.id.in_(dish_ids)).all()
    dish_map = {d.id: d for d in dishes}

    result = []
    total = Decimal('0.00')
    for did_str, qty in items.items():
        did = int(did_str)
        dish = dish_map.get(did)
        if not dish:
            continue
        # 如果include_zero为False，跳过数量为0的菜品
        if not include_zero and qty <= 0:
            continue
        line_total = Decimal(str(dish.price)) * max(0, qty)  # 确保小计不为负
        # 只有数量>0的菜品才计入总价
        if qty > 0:
            total += line_total
        result.append({
            'dish': dish,
            'quantity': qty,
            'line_total': line_total
        })

    return result, total


def is_blacklisted(restaurant: Restaurant, user: User) -> bool:
    if not restaurant or not user:
        return False
    return user in restaurant.blacklisted_users


def call_gpt(system_prompt: str, user_content: str) -> str:
    """调用 GPT 接口，返回回答文本"""
    if not GPT_API_KEY:
        return "当前系统未配置 GPT_API_KEY，无法使用智能问答功能。"

    try:
        url = GPT_BASE_URL.rstrip('/') + '/chat/completions'
        headers = {
            'Authorization': f'Bearer {GPT_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': GPT_MODEL,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_content}
            ]
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        print("GPT error:", repr(e))
        return "智能问答服务暂时不可用，请稍后再试。"


def build_restaurant_stats_text(restaurant: Restaurant) -> str:
    """构建给顾问看的餐厅统计信息文本"""
    # 总订单数 & 总销售额
    total_orders = Order.query.filter_by(restaurant_id=restaurant.id).count()
    total_amount = db.session.query(func.coalesce(func.sum(Order.total_amount), 0))\
        .filter(Order.restaurant_id == restaurant.id).scalar() or 0

    # TOP 客人
    top_customers = db.session.query(
        User.username,
        func.sum(Order.total_amount).label('total')
    ).join(Order, Order.customer_id == User.id)\
     .filter(Order.restaurant_id == restaurant.id)\
     .group_by(User.id)\
     .order_by(func.sum(Order.total_amount).desc())\
     .limit(5).all()

    # TOP 菜品（按份数）
    top_dishes_qty = db.session.query(
        Dish.name,
        func.coalesce(func.sum(OrderItem.quantity), 0).label('qty')
    ).join(OrderItem, OrderItem.dish_id == Dish.id)\
     .filter(Dish.restaurant_id == restaurant.id)\
     .group_by(Dish.id)\
     .order_by(func.sum(OrderItem.quantity).desc())\
     .limit(5).all()

    # TOP 菜品（按金额）
    top_dishes_amount = db.session.query(
        Dish.name,
        func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0).label('amt')
    ).join(OrderItem, OrderItem.dish_id == Dish.id)\
     .filter(Dish.restaurant_id == restaurant.id)\
     .group_by(Dish.id)\
     .order_by(func.sum(OrderItem.quantity * OrderItem.unit_price).desc())\
     .limit(5).all()

    lines = [
        f"餐厅名称：{restaurant.name}",
        f"总订单数：{total_orders}",
        f"总销售额：{total_amount} 元",
        "",
        "Top 5 客人（按消费额）："
    ]
    if not top_customers:
        lines.append("暂无消费记录。")
    else:
        for idx, (name, total) in enumerate(top_customers, start=1):
            lines.append(f"{idx}. {name} - {total} 元")

    lines.append("")
    lines.append("Top 5 菜品（按份数）：")
    if not top_dishes_qty:
        lines.append("暂无菜品被点。")
    else:
        for idx, (name, qty) in enumerate(top_dishes_qty, start=1):
            lines.append(f"{idx}. {name} - {qty} 份")

    lines.append("")
    lines.append("Top 5 菜品（按销售额）：")
    if not top_dishes_amount:
        lines.append("暂无菜品销售额数据。")
    else:
        for idx, (name, amt) in enumerate(top_dishes_amount, start=1):
            lines.append(f"{idx}. {name} - {amt} 元")

    return "\n".join(lines)


def build_menu_stats_text(restaurant: Restaurant) -> str:
    """构建菜品列表统计给 GPT（菜品顾问用）"""
    dishes = Dish.query.filter_by(restaurant_id=restaurant.id).all()
    if not dishes:
        return "当前餐厅还没有任何菜品。"

    lines = [f"餐厅名称：{restaurant.name}", "菜品列表："]
    for dish in dishes:
        total_qty = db.session.query(func.coalesce(func.sum(OrderItem.quantity), 0))\
            .filter(OrderItem.dish_id == dish.id).scalar() or 0
        lines.append(
            f"- 菜品ID: {dish.id}, 名称: {dish.name}, 分类: {dish.category.name}, "
            f"价格: {dish.price} 元, 被点份数: {total_qty} 份, 简介: {dish.description or '无'}"
        )
    return "\n".join(lines)


# ----------------- 视图：认证 -----------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')
        avatar_file = request.files.get('avatar')

        if not username or not password:
            flash('用户名和密码必填', 'danger')
            return redirect(url_for('register'))
        if password != password2:
            flash('两次输入的密码不一致', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash('用户名已存在，请换一个', 'danger')
            return redirect(url_for('register'))
        
        # 验证头像是否上传
        if not avatar_file or not avatar_file.filename:
            flash('头像为必填项，请上传头像', 'danger')
            return redirect(url_for('register'))

        try:
            avatar_path = save_avatar(avatar_file)
            if not avatar_path:
                flash('头像上传失败，请重试', 'danger')
                return redirect(url_for('register'))
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('register'))

        user = User(username=username, email=None, avatar=avatar_path)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('注册成功，请登录', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            flash('用户名或密码错误', 'danger')
            return redirect(url_for('login'))

        login_user(user)
        flash('登录成功，欢迎回来～', 'success')
        return redirect(url_for('dashboard'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('您已退出登录', 'info')
    return redirect(url_for('login'))


# ----------------- 视图：主页 / 仪表盘 -----------------

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')


# ----------------- 视图：管理餐厅 -----------------

DEFAULT_CATEGORY_NAMES = ['饮品', '菜品', '主食', '小吃']


def create_default_categories(restaurant: Restaurant):
    existing = {c.name for c in restaurant.categories}
    for name in DEFAULT_CATEGORY_NAMES:
        if name not in existing:
            db.session.add(Category(name=name, restaurant_id=restaurant.id))
    db.session.commit()


@app.route('/manage/restaurant', methods=['GET', 'POST'])
@login_required
def manage_restaurant():
    restaurant = current_user.restaurant

    if request.method == 'POST' and not restaurant:
        # 创建餐厅
        name = request.form.get('name', '').strip()
        logo_file = request.files.get('logo')

        if not name:
            flash('餐厅名称必填', 'danger')
            return redirect(url_for('manage_restaurant'))
        if Restaurant.query.filter_by(name=name).first():
            flash('餐厅名称已存在，请换一个', 'danger')
            return redirect(url_for('manage_restaurant'))

        # 验证Logo是否上传
        if not logo_file or not logo_file.filename:
            flash('请上传餐厅Logo', 'danger')
            return redirect(url_for('manage_restaurant'))

        try:
            logo_path = save_logo(logo_file)
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(url_for('manage_restaurant'))

        restaurant = Restaurant(name=name, logo=logo_path, owner=current_user)
        db.session.add(restaurant)
        db.session.commit()
        create_default_categories(restaurant)
        flash('餐厅创建成功，接下来可以添加菜品啦～', 'success')
        return redirect(url_for('manage_restaurant'))

    # GET
    if restaurant:
        create_default_categories(restaurant)
    return render_template('manage_restaurant.html', restaurant=restaurant)


@app.route('/manage/dishes')
@login_required
def manage_dishes():
    restaurant = current_user.restaurant
    if not restaurant:
        flash('请先创建餐厅', 'warning')
        return redirect(url_for('manage_restaurant'))

    categories = Category.query.filter_by(restaurant_id=restaurant.id).all()

    # 每个菜品的统计：总份数、不同顾客数
    dish_stats = {}
    rows = db.session.query(
        Dish.id,
        func.coalesce(func.sum(OrderItem.quantity), 0).label('qty'),
        func.count(func.distinct(Order.customer_id)).label('user_count')
    ).join(OrderItem, OrderItem.dish_id == Dish.id, isouter=True)\
     .join(Order, OrderItem.order_id == Order.id, isouter=True)\
     .filter(Dish.restaurant_id == restaurant.id)\
     .group_by(Dish.id).all()
    for did, qty, user_count in rows:
        dish_stats[did] = {'qty': qty or 0, 'user_count': user_count or 0}

    return render_template(
        'manage_dishes.html',
        restaurant=restaurant,
        categories=categories,
        dish_stats=dish_stats
    )


@app.route('/manage/dish/add/<int:category_id>', methods=['GET', 'POST'])
@login_required
def add_dish(category_id):
    restaurant = current_user.restaurant
    if not restaurant:
        flash('请先创建餐厅', 'warning')
        return redirect(url_for('manage_restaurant'))

    category = Category.query.get_or_404(category_id)
    if category.restaurant_id != restaurant.id:
        flash('无权在其他餐厅添加菜品', 'danger')
        return redirect(url_for('manage_dishes'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price_str = request.form.get('price', '').strip()
        description = request.form.get('description', '').strip()
        image_file = request.files.get('image')

        if not name or not price_str:
            flash('菜品名称和价格必填', 'danger')
            return redirect(request.url)
        if len(description) > 500:
            flash('菜品介绍不能超过 500 字', 'danger')
            return redirect(request.url)

        try:
            price = Decimal(price_str)
            if price <= 0:
                raise Exception()
        except Exception:
            flash('价格格式不正确', 'danger')
            return redirect(request.url)

        # 验证图片是否上传（新建菜品时必须上传）
        if not image_file or not image_file.filename:
            flash('请上传菜品图片', 'danger')
            return redirect(request.url)

        try:
            big_path, thumb_path = save_dish_images(image_file)
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(request.url)

        dish = Dish(
            name=name,
            description=description,
            price=price,
            image=big_path,
            thumb=thumb_path,
            restaurant_id=restaurant.id,
            category_id=category.id
        )
        db.session.add(dish)
        db.session.commit()
        flash('菜品添加成功', 'success')
        return redirect(url_for('manage_dishes'))

    return render_template('dish_form.html', mode='add', category=category, dish=None)


@app.route('/manage/dish/<int:dish_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_dish(dish_id):
    restaurant = current_user.restaurant
    if not restaurant:
        flash('请先创建餐厅', 'warning')
        return redirect(url_for('manage_restaurant'))

    dish = Dish.query.get_or_404(dish_id)
    if dish.restaurant_id != restaurant.id:
        flash('无权编辑其他餐厅的菜品', 'danger')
        return redirect(url_for('manage_dishes'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        price_str = request.form.get('price', '').strip()
        description = request.form.get('description', '').strip()
        image_file = request.files.get('image')

        if not name or not price_str:
            flash('菜品名称和价格必填', 'danger')
            return redirect(request.url)
        if len(description) > 500:
            flash('菜品介绍不能超过 500 字', 'danger')
            return redirect(request.url)

        try:
            price = Decimal(price_str)
            if price <= 0:
                raise Exception()
        except Exception:
            flash('价格格式不正确', 'danger')
            return redirect(request.url)

        dish.name = name
        dish.price = price
        dish.description = description

        if image_file and image_file.filename:
            try:
                big_path, thumb_path = save_dish_images(image_file)
            except ValueError as e:
                flash(str(e), 'danger')
                return redirect(request.url)
            dish.image = big_path
            dish.thumb = thumb_path

        db.session.commit()
        flash('菜品修改成功', 'success')
        return redirect(url_for('manage_dishes'))

    return render_template('dish_form.html', mode='edit', dish=dish, category=dish.category)


@app.route('/manage/dish/<int:dish_id>/delete', methods=['POST'])
@login_required
def delete_dish(dish_id):
    restaurant = current_user.restaurant
    if not restaurant:
        flash('请先创建餐厅', 'warning')
        return redirect(url_for('manage_restaurant'))

    dish = Dish.query.get_or_404(dish_id)
    if dish.restaurant_id != restaurant.id:
        flash('无权删除其他餐厅的菜品', 'danger')
        return redirect(url_for('manage_dishes'))

    # 获取所有包含该菜品的订单
    affected_orders = db.session.query(Order).join(OrderItem).filter(
        OrderItem.dish_id == dish.id
    ).distinct().all()
    
    # 删除相关点餐记录（OrderItem）
    OrderItem.query.filter_by(dish_id=dish.id).delete()
    db.session.delete(dish)
    db.session.commit()

    # 重新计算受影响订单的总金额
    for order in affected_orders:
        # 重新计算该订单的总金额
        new_total = db.session.query(
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0)
        ).filter(OrderItem.order_id == order.id).scalar() or Decimal('0.00')
        order.total_amount = new_total
    
    db.session.commit()

    # 清理空订单（没有订单项的订单）
    empty_orders = Order.query.outerjoin(OrderItem).filter(OrderItem.id.is_(None)).all()
    for od in empty_orders:
        db.session.delete(od)
    db.session.commit()

    flash('菜品及相关点餐记录已删除，订单总金额已更新', 'info')
    return redirect(url_for('manage_dishes'))


@app.route('/manage/dish/<int:dish_id>')
@login_required
def manage_dish_detail(dish_id):
    restaurant = current_user.restaurant
    if not restaurant:
        flash('请先创建餐厅', 'warning')
        return redirect(url_for('manage_restaurant'))

    dish = Dish.query.get_or_404(dish_id)
    if dish.restaurant_id != restaurant.id:
        flash('无权查看其他餐厅的菜品', 'danger')
        return redirect(url_for('manage_dishes'))

    # 总份数
    total_qty = db.session.query(func.coalesce(func.sum(OrderItem.quantity), 0))\
        .filter(OrderItem.dish_id == dish.id).scalar() or 0

    # 每个顾客为该菜点了多少，花了多少钱
    customer_rows = db.session.query(
        User,
        func.coalesce(func.sum(OrderItem.quantity), 0).label('qty'),
        func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0).label('amount')
    ).join(Order, Order.customer_id == User.id)\
     .join(OrderItem, OrderItem.order_id == Order.id)\
     .filter(OrderItem.dish_id == dish.id, Order.restaurant_id == restaurant.id)\
     .group_by(User.id).all()

    return render_template(
        'manage_dish_detail.html',
        restaurant=restaurant,
        dish=dish,
        total_qty=total_qty,
        customer_rows=customer_rows
    )


@app.route('/manage/customers')
@login_required
def manage_customers():
    restaurant = current_user.restaurant
    if not restaurant:
        flash('请先创建餐厅', 'warning')
        return redirect(url_for('manage_restaurant'))

    rows = db.session.query(
        User,
        func.coalesce(func.sum(Order.total_amount), 0).label('total_amount')
    ).join(Order, Order.customer_id == User.id)\
     .filter(Order.restaurant_id == restaurant.id)\
     .group_by(User.id)\
     .order_by(func.sum(Order.total_amount).desc()).all()

    return render_template(
        'manage_customers.html',
        restaurant=restaurant,
        rows=rows
    )


@app.route('/manage/customer/<int:user_id>')
@login_required
def customer_history(user_id):
    restaurant = current_user.restaurant
    if not restaurant:
        flash('请先创建餐厅', 'warning')
        return redirect(url_for('manage_restaurant'))

    user = User.query.get_or_404(user_id)

    dish_rows = db.session.query(
        Dish,
        func.coalesce(func.sum(OrderItem.quantity), 0).label('qty'),
        func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0).label('amount')
    ).join(OrderItem, OrderItem.dish_id == Dish.id)\
     .join(Order, OrderItem.order_id == Order.id)\
     .filter(Order.customer_id == user.id, Order.restaurant_id == restaurant.id)\
     .group_by(Dish.id).all()

    total_amount = db.session.query(
        func.coalesce(func.sum(Order.total_amount), 0)
    ).filter(Order.customer_id == user.id, Order.restaurant_id == restaurant.id).scalar() or 0

    return render_template(
        'customer_history.html',
        restaurant=restaurant,
        user=user,
        dish_rows=dish_rows,
        total_amount=total_amount
    )


@app.route('/manage/customer/<int:user_id>/toggle_blacklist', methods=['POST'])
@login_required
def toggle_blacklist(user_id):
    restaurant = current_user.restaurant
    if not restaurant:
        flash('请先创建餐厅', 'warning')
        return redirect(url_for('manage_restaurant'))

    user = User.query.get_or_404(user_id)
    if user in restaurant.blacklisted_users:
        restaurant.blacklisted_users.remove(user)
        db.session.commit()
        flash(f'已将 {user.username} 从黑名单移除', 'info')
    else:
        restaurant.blacklisted_users.append(user)
        db.session.commit()
        flash(f'已将 {user.username} 加入黑名单', 'warning')

    return redirect(url_for('manage_customers'))


def generate_chart_colors(n):
    """生成n个不同的颜色，使用HSL色彩空间确保颜色分布均匀"""
    colors = []
    for i in range(n):
        # 使用HSL色彩空间，色相均匀分布，饱和度和亮度保持适中
        hue = i / n  # 色相：0-1之间均匀分布
        saturation = 0.7 + (i % 3) * 0.1  # 饱和度：0.7-0.9之间变化
        lightness = 0.5 + (i % 2) * 0.1  # 亮度：0.5-0.6之间变化
        rgb = colorsys.hls_to_rgb(hue, lightness, saturation)
        # 转换为RGB 0-255格式
        r, g, b = [int(c * 255) for c in rgb]
        colors.append(f'rgb({r}, {g}, {b})')
    return colors


@app.route('/manage/reports')
@login_required
def manage_reports():
    restaurant = current_user.restaurant
    if not restaurant:
        flash('请先创建餐厅', 'warning')
        return redirect(url_for('manage_restaurant'))

    dish_rows = db.session.query(
        Dish,
        func.coalesce(func.sum(OrderItem.quantity), 0).label('qty'),
        func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0).label('amount')
    ).join(OrderItem, OrderItem.dish_id == Dish.id, isouter=True)\
     .filter(Dish.restaurant_id == restaurant.id)\
     .group_by(Dish.id).all()

    # 将数据转换为列表并排序（按份数降序）
    dish_data = [(d.name, int(qty), float(amount)) for d, qty, amount in dish_rows]
    dish_data.sort(key=lambda x: x[1], reverse=True)  # 按份数排序
    
    labels = [name for name, _, _ in dish_data]
    qty_data = [qty for _, qty, _ in dish_data]
    amount_data = [amount for _, _, amount in dish_data]
    
    # 按销售额排序（用于金额图表）
    dish_data_amount = sorted(dish_data, key=lambda x: x[2], reverse=True)
    labels_amount = [name for name, _, _ in dish_data_amount]
    amount_data_sorted = [amount for _, _, amount in dish_data_amount]

    total_qty = sum(qty_data)
    total_amount = sum(amount_data)
    
    # 生成足够的颜色
    num_dishes = len(labels)
    colors = generate_chart_colors(num_dishes)

    return render_template(
        'manage_reports.html',
        restaurant=restaurant,
        labels=labels,
        qty_data=qty_data,
        amount_data=amount_data,
        labels_amount=labels_amount,
        amount_data_sorted=amount_data_sorted,
        total_qty=total_qty,
        total_amount=total_amount,
        colors=colors
    )


@app.route('/manage/advisor', methods=['GET', 'POST'])
@login_required
def manage_advisor():
    restaurant = current_user.restaurant
    if not restaurant:
        flash('请先创建餐厅', 'warning')
        return redirect(url_for('manage_restaurant'))

    answer = None
    question = None

    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        if not question:
            flash('请先输入要咨询的问题', 'warning')
        else:
            stats_text = build_restaurant_stats_text(restaurant)
            system_prompt = (
                "你是一位经验丰富的餐厅经营顾问，擅长数据分析、市场洞察和经营策略制定。"
                "你的回答应该：\n"
                "1. 基于提供的真实统计数据进行分析，给出具体的数据支撑\n"
                "2. 用简体中文、条理清晰地回答，使用分段和要点来组织内容\n"
                "3. 如果问题涉及具体顾客或菜品，要引用数据中的具体信息（如姓名、金额、数量等）\n"
                "4. 提供实用的建议和洞察，帮助老板做出更好的经营决策\n"
                "5. 使用**粗体**来突出重要信息，使用*斜体*来强调次要信息\n"
                "6. 回答要专业但友好，避免过于技术化的术语\n"
                "7. 如果数据不足，要诚实说明，并给出基于经验的建议"
            )
            user_content = f"餐厅数据如下：\n{stats_text}\n\n老板的问题是：{question}"
            answer = call_gpt(system_prompt, user_content)

    return render_template(
        'manage_advisor.html',
        restaurant=restaurant,
        question=question,
        answer=answer
    )


# ----------------- 视图：点餐部分 -----------------

@app.route('/restaurants')
@login_required
def restaurants():
    # 按销售额排序
    rows = db.session.query(
        Restaurant,
        func.coalesce(func.sum(Order.total_amount), 0).label('revenue')
    ).outerjoin(Order, Order.restaurant_id == Restaurant.id)\
     .group_by(Restaurant.id)\
     .order_by(func.sum(Order.total_amount).desc()).all()

    return render_template('restaurants_list.html', rows=rows)


@app.route('/restaurant/<int:restaurant_id>')
@login_required
def restaurant_menu(restaurant_id):
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    session['last_restaurant_id'] = restaurant_id

    if is_blacklisted(restaurant, current_user):
        flash('您已被本餐厅加入黑名单，可以浏览但无法下单。', 'danger')

    categories = Category.query.filter_by(restaurant_id=restaurant.id).all()
    selected_category_id = request.args.get('category_id', type=int)
    if categories and not selected_category_id:
        selected_category_id = categories[0].id

    dishes = []
    if selected_category_id:
        dishes = Dish.query.filter_by(
            restaurant_id=restaurant.id,
            category_id=selected_category_id
        ).all()

    return render_template(
        'restaurant_menu.html',
        restaurant=restaurant,
        categories=categories,
        selected_category_id=selected_category_id,
        dishes=dishes
    )


@app.route('/restaurant/<int:restaurant_id>/dish/<int:dish_id>', methods=['GET', 'POST'])
@login_required
def dish_detail(restaurant_id, dish_id):
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    dish = Dish.query.get_or_404(dish_id)
    if dish.restaurant_id != restaurant.id:
        flash('该菜品不属于当前餐厅', 'danger')
        return redirect(url_for('restaurant_menu', restaurant_id=restaurant_id))

    session['last_restaurant_id'] = restaurant_id

    question = None
    answer = None

    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        if not question:
            flash('请输入想要咨询的问题', 'warning')
        else:
            menu_text = build_menu_stats_text(restaurant)
            system_prompt = (
                "你是一位专业的餐厅点餐顾问，擅长帮助顾客选择适合的菜品。"
                "你的回答应该：\n"
                "1. 优先围绕顾客当前浏览的菜品回答，但如果顾客明确提到其他菜品，要综合考虑整个菜单\n"
                "2. 使用简体中文，语气友好、亲切，像朋友一样给出建议\n"
                "3. 结合菜品数据（价格、被点次数、评价等）来回答，让建议更有说服力\n"
                "4. 如果顾客询问菜品特点、搭配建议、口味等，要基于菜单信息给出具体建议\n"
                "5. 使用**粗体**来突出重要信息，使用*斜体*来强调次要信息\n"
                "6. 回答要简洁明了，避免冗长，但要有足够的信息帮助顾客做决定\n"
                "7. 如果数据不足，可以基于菜品名称和分类给出合理的建议"
            )
            user_content = (
                f"完整菜单和销售数据如下：\n{menu_text}\n\n"
                f"顾客当前正在查看的菜品是：{dish.name}（ID: {dish.id}）。\n"
                f"顾客的问题是：{question}"
            )
            answer = call_gpt(system_prompt, user_content)

    return render_template(
        'dish_detail.html',
        restaurant=restaurant,
        dish=dish,
        question=question,
        answer=answer
    )


@app.route('/add_to_cart/<int:dish_id>', methods=['POST'])
@login_required
def add_to_cart_route(dish_id):
    dish = Dish.query.get_or_404(dish_id)
    restaurant = dish.restaurant

    if is_blacklisted(restaurant, current_user):
        flash('抱歉，您已被本餐厅加入黑名单，无法下单。', 'danger')
        return redirect(request.referrer or url_for('restaurant_menu', restaurant_id=restaurant.id))

    quantity = request.form.get('quantity', 1, type=int)
    if quantity <= 0:
        quantity = 1
    add_to_cart(dish_id, quantity)
    flash(f'已将 {dish.name} 加入您的餐桌', 'success')
    return redirect(request.referrer or url_for('restaurant_menu', restaurant_id=restaurant.id))


@app.route('/restaurant/<int:restaurant_id>/my_table')
@login_required
def my_table(restaurant_id):
    restaurant = Restaurant.query.get_or_404(restaurant_id)
    session['last_restaurant_id'] = restaurant_id
    # 显示所有菜品，包括数量为0的
    cart_items, total = get_cart_items_for_restaurant(restaurant_id, include_zero=True)

    return render_template(
        'my_table.html',
        restaurant=restaurant,
        cart_items=cart_items,
        total=total
    )


@app.route('/update_cart/<int:restaurant_id>/<int:dish_id>', methods=['POST'])
@login_required
def update_cart(restaurant_id, dish_id):
    dish = Dish.query.get_or_404(dish_id)
    if dish.restaurant_id != restaurant_id:
        flash('菜品不属于该餐厅', 'danger')
        return redirect(url_for('my_table', restaurant_id=restaurant_id))

    cart = get_cart()
    rid = str(restaurant_id)
    did = str(dish_id)
    action = request.form.get('action')

    if rid not in cart or did not in cart[rid]:
        flash('您的餐桌中没有该菜品', 'warning')
        return redirect(url_for('my_table', restaurant_id=restaurant_id))

    if action == 'inc':
        cart[rid][did] += 1
    elif action == 'dec':
        cart[rid][did] -= 1
        # 不再删除数量为0的菜品，保留在购物车中
        if cart[rid][did] < 0:
            cart[rid][did] = 0

    save_cart(cart)
    return redirect(url_for('my_table', restaurant_id=restaurant_id))


@app.route('/restaurant/<int:restaurant_id>/checkout', methods=['POST'])
@login_required
def checkout(restaurant_id):
    restaurant = Restaurant.query.get_or_404(restaurant_id)

    if is_blacklisted(restaurant, current_user):
        flash('抱歉，您已被本餐厅加入黑名单，无法付款。', 'danger')
        return redirect(url_for('my_table', restaurant_id=restaurant_id))

    # 结账时只获取数量>0的菜品
    cart_items, total = get_cart_items_for_restaurant(restaurant_id, include_zero=False)
    if not cart_items:
        flash('您的餐桌是空的，请先点菜', 'warning')
        return redirect(url_for('restaurant_menu', restaurant_id=restaurant_id))

    # 创建订单和订单明细
    order = Order(
        customer_id=current_user.id,
        restaurant_id=restaurant_id,
        total_amount=total
    )
    db.session.add(order)
    db.session.flush()  # 先获取订单 ID

    for entry in cart_items:
        dish = entry['dish']
        qty = entry['quantity']
        # 只创建数量>0的订单项
        if qty > 0:
            item = OrderItem(
                order_id=order.id,
                dish_id=dish.id,
                quantity=qty,
                unit_price=dish.price
            )
            db.session.add(item)

    db.session.commit()

    # 清空该餐厅的购物车
    cart = get_cart()
    rid = str(restaurant_id)
    if rid in cart:
        del cart[rid]
        save_cart(cart)

    flash('付款成功，祝您用餐愉快！', 'success')
    return render_template(
        'checkout_success.html',
        restaurant=restaurant,
        order=order,
        cart_items=cart_items,
        total=total
    )


# ----------------- CLI & 入口 -----------------

@app.cli.command('init-db')
def init_db_cmd():
    """初始化数据库"""
    db.create_all()
    print("数据库已初始化。")


if __name__ == '__main__':
    ensure_upload_dirs()
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5001, debug=True)
