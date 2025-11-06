from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
import config
from math import ceil
from datetime import datetime
import pandas as pd
from io import BytesIO

# -------------------------------
# Initialisation de l'application
# -------------------------------
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Utilisation de SQLite pour les tests
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///linge_maison.sqlite3'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuration Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'votre-email@example.com'
app.config['MAIL_PASSWORD'] = 'votre_mot_de_passe_application'
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True

mail = Mail(app)
db = SQLAlchemy(app)

# -------------------------------
# Modèles de base de données adaptés au linge de maison
# -------------------------------
class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    categorie = db.Column(db.String(100), nullable=False)  # Draps, Serviettes, Couettes, etc.
    material = db.Column(db.String(100))  # Coton, Lin, Polyester, etc.
    size = db.Column(db.String(100))  # 140x200, 160x200, etc.
    color = db.Column(db.String(50))  # Blanc, Bleu, Rouge, etc.
    stock_quantity = db.Column(db.Integer, default=0)
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relation avec les images
    images = db.relationship('ProductImage', backref='product', lazy=True, cascade="all, delete-orphan")

class ProductImage(db.Model):
    __tablename__ = 'product_images'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    image_url = db.Column(db.Text, nullable=False)
    alt_text = db.Column(db.String(255))
    is_primary = db.Column(db.Boolean, default=False)  # Image principale
    display_order = db.Column(db.Integer, default=0)  # Ordre d'affichage

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    paypal_id = db.Column(db.String(100))          
    is_paid = db.Column(db.Boolean, default=False)
    product = db.relationship('Product')

class Offer(db.Model):
    __tablename__ = 'offers'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255))
    description = db.Column(db.Text)
    image_url = db.Column(db.Text)
    link = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

class ClientRequest(db.Model):
    __tablename__ = 'client_requests'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    whatsapp = db.Column(db.String(50))
    message = db.Column(db.Text)
    quantity = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_processed = db.Column(db.Boolean, default=False)
    product = db.relationship('Product')

# Import des identifiants admin depuis config.py
ADMIN_USERNAME = config.ADMIN_USERNAME
ADMIN_PASSWORD = config.ADMIN_PASSWORD

# -------------------------------
# Routes publiques
# -------------------------------
@app.route('/')
def index():
    categories = db.session.query(Product.categorie).distinct().all()
    page = request.args.get('page', 1, type=int)
    per_page = 8
    products = Product.query.filter_by(is_available=True).paginate(page=page, per_page=per_page, error_out=False)
    offers = Offer.query.filter_by(is_active=True).all()
    return render_template('index.html', products=products, categories=categories, offers=offers)

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('query', '')
    categories = db.session.query(Product.categorie).distinct().all()
    page = request.args.get('page', 1, type=int)
    per_page = 6
    products = Product.query.filter(
        Product.title.ilike(f'%{query}%'),
        Product.is_available == True
    ).paginate(page=page, per_page=per_page, error_out=False)
    offers = Offer.query.filter_by(is_active=True).all()
    return render_template('search.html', products=products, categories=categories, offers=offers, query=query)

@app.route('/category/<categorie>')
def category_view(categorie):
    categories = db.session.query(Product.categorie).distinct().all()
    page = request.args.get('page', 1, type=int)
    per_page = 6
    search = request.args.get('search', '').strip()
    query = Product.query.filter_by(categorie=categorie, is_available=True)
    offers = Offer.query.filter_by(is_active=True).all()
    if search:
        query = query.filter(Product.title.ilike(f'%{search}%'))
    products = query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('category.html', products=products, categorie=categorie, categories=categories, offers=offers, search=search)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    categories = db.session.query(Product.categorie).distinct().all()
    product = Product.query.get_or_404(product_id)
    # Récupérer toutes les images du produit triées par ordre d'affichage
    images = ProductImage.query.filter_by(product_id=product_id).order_by(ProductImage.display_order).all()
    return render_template('product_detail.html', categories=categories, product=product, images=images)

@app.route('/checkout/<int:product_id>', methods=["GET", "POST"])
def checkout(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == "POST":
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        country = request.form['country']
        city = request.form['city']
        address = request.form['address']
        phone = request.form['phone']
        whatsapp = request.form['whatsapp']
        message = request.form['message']
        quantity = int(request.form['quantity'])
        
        client_req = ClientRequest()
        client_req.product_id = product.id
        client_req.first_name = first_name
        client_req.last_name = last_name
        client_req.country = country
        client_req.city = city
        client_req.address = address
        client_req.phone = phone
        client_req.whatsapp = whatsapp
        client_req.message = message
        client_req.quantity = quantity
        client_req.is_processed = False
        db.session.add(client_req)
        db.session.commit()
        flash("✅ Votre demande a été envoyée avec succès, nous vous contacterons bientôt.")
        return redirect(url_for('checkout', product_id=product.id))
    return render_template('checkout.html', product=product)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

# -------------------------------
# Routes admin
# -------------------------------
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USERNAME and request.form['password'] == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('admin_panel'))
        else:
            flash('Identifiants incorrects.')
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('admin_login'))

@app.route('/admin')
def admin_panel():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    page = request.args.get('page', 1, type=int)
    per_page = 10
    products = Product.query.paginate(page=page, per_page=per_page, error_out=False)
    offers = Offer.query.paginate(page=page, per_page=per_page, error_out=False)
    return render_template('admin_panel.html', products=products, offers=offers)

@app.route('/admin/add', methods=['GET', 'POST'])
def admin_add():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        new_product = Product()
        new_product.title = request.form['title']
        new_product.description = request.form['description']
        new_product.price = request.form['price']
        new_product.categorie = request.form['categorie']
        new_product.material = request.form.get('material')
        new_product.size = request.form.get('size')
        new_product.color = request.form.get('color')
        new_product.stock_quantity = int(request.form.get('stock_quantity', 0))
        db.session.add(new_product)
        db.session.flush()  # Pour obtenir l'ID du produit
        
        # Ajouter les images
        image_urls = request.form.getlist('image_urls')
        for i, url in enumerate(image_urls):
            if url.strip():
                image = ProductImage()
                image.product_id = new_product.id
                image.image_url = url.strip()
                image.is_primary = (i == 0)
                image.display_order = i
                db.session.add(image)
        
        db.session.commit()
        return redirect(url_for('admin_panel'))
    return render_template('admin_form.html', action='Ajouter')

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
def admin_edit(id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    product = Product.query.get_or_404(id)
    if request.method == 'POST':
        product.title = request.form['title']
        product.description = request.form['description']
        product.price = request.form['price']
        product.categorie = request.form['categorie']
        product.material = request.form.get('material')
        product.size = request.form.get('size')
        product.color = request.form.get('color')
        product.stock_quantity = int(request.form.get('stock_quantity', 0))
        
        # Supprimer les anciennes images
        ProductImage.query.filter_by(product_id=product.id).delete()
        
        # Ajouter les nouvelles images
        image_urls = request.form.getlist('image_urls')
        for i, url in enumerate(image_urls):
            if url.strip():
                image = ProductImage()
                image.product_id = product.id
                image.image_url = url.strip()
                image.is_primary = (i == 0)
                image.display_order = i
                db.session.add(image)
        
        db.session.commit()
        return redirect(url_for('admin_panel'))
    return render_template('admin_form.html', product=product, action='Modifier')

@app.route('/admin/delete/<int:id>', methods=['POST'])
def admin_delete(id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/comments')
def admin_comments():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    query = ClientRequest.query
    product = request.args.get('product')
    first_name = request.args.get('first_name')
    last_name = request.args.get('last_name')
    country = request.args.get('country')
    city = request.args.get('city')
    processed = request.args.get('processed')
    
    if product:
        query = query.join(Product).filter(Product.title.ilike(f'%{product}%'))
    if first_name:
        query = query.filter(ClientRequest.first_name.ilike(f'%{first_name}%'))
    if last_name:
        query = query.filter(ClientRequest.last_name.ilike(f'%{last_name}%'))
    if country:
        query = query.filter(ClientRequest.country.ilike(f'%{country}%'))
    if city:
        query = query.filter(ClientRequest.city.ilike(f'%{city}%'))
    if processed is not None:
        if processed == 'true':
            query = query.filter(ClientRequest.is_processed == True)
        elif processed == 'false':
            query = query.filter(ClientRequest.is_processed == False)
    
    sort_by = request.args.get('sort_by', 'created_at')
    order = request.args.get('order', 'desc')
    
    if sort_by == 'name':
        if order == 'asc':
            query = query.order_by(ClientRequest.first_name.asc())
        else:
            query = query.order_by(ClientRequest.first_name.desc())
    elif sort_by == 'status':
        if order == 'asc':
            query = query.order_by(ClientRequest.is_processed.asc())
        else:
            query = query.order_by(ClientRequest.is_processed.desc())
    elif sort_by == 'product':
        if order == 'asc':
            query = query.order_by(Product.title.asc())
        else:
            query = query.order_by(Product.title.desc())
    else:
        if order == 'asc':
            query = query.order_by(ClientRequest.created_at.asc())
        else:
            query = query.order_by(ClientRequest.created_at.desc())
    
    comments = query.all()
    return render_template('admin_comments.html', comments=comments, sort_by=sort_by, order=order)

@app.route('/admin/toggle_request/<int:request_id>')
def toggle_request(request_id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    client_request = ClientRequest.query.get_or_404(request_id)
    client_request.is_processed = not client_request.is_processed
    db.session.commit()
    return redirect(url_for('admin_comments'))

# -------------------------------
# CRUD pour offres spéciales
# -------------------------------
@app.route('/admin/offer/add', methods=['GET', 'POST'])
def add_offer():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        new_offer = Offer()
        new_offer.title = request.form['title']
        new_offer.description = request.form['description']
        new_offer.image_url = request.form['image_url']
        new_offer.link = request.form.get('link')
        new_offer.is_active = True
        db.session.add(new_offer)
        db.session.commit()
        flash('Offre ajoutée avec succès!')
        return redirect(url_for('admin_panel'))
    return redirect(url_for('admin_panel'))

@app.route('/admin/offer/edit/<int:id>', methods=['GET', 'POST'])
def edit_offer(id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    offer = Offer.query.get_or_404(id)
    if request.method == 'POST':
        offer.title = request.form['title']
        offer.description = request.form['description']
        offer.image_url = request.form['image_url']
        offer.link = request.form.get('link')
        db.session.commit()
        flash('Offre modifiée avec succès!')
        return redirect(url_for('admin_panel'))
    return redirect(url_for('admin_panel'))

@app.route('/admin/offer/delete/<int:id>', methods=['POST'])
def delete_offer(id):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    offer = Offer.query.get_or_404(id)
    db.session.delete(offer)
    db.session.commit()
    flash('Offre supprimée avec succès!')
    return redirect(url_for('admin_panel'))

@app.route('/admin/export_comments_excel')
def export_comments_excel():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    query = ClientRequest.query.order_by(ClientRequest.created_at.desc())
    
    # Filtres
    product = request.args.get('product')
    first_name = request.args.get('first_name')
    last_name = request.args.get('last_name')
    country = request.args.get('country')
    city = request.args.get('city')
    processed = request.args.get('processed')
    
    if product:
        query = query.join(Product).filter(Product.title.ilike(f'%{product}%'))
    if first_name:
        query = query.filter(ClientRequest.first_name.ilike(f'%{first_name}%'))
    if last_name:
        query = query.filter(ClientRequest.last_name.ilike(f'%{last_name}%'))
    if country:
        query = query.filter(ClientRequest.country.ilike(f'%{country}%'))
    if city:
        query = query.filter(ClientRequest.city.ilike(f'%{city}%'))
    if processed is not None:
        if processed == 'true':
            query = query.filter(ClientRequest.is_processed == True)
        elif processed == 'false':
            query = query.filter(ClientRequest.is_processed == False)
    
    data = []
    for req in query.all():
        data.append({
            'ID': req.id,
            'Produit': req.product.title,
            'Quantité': req.quantity,
            'Prénom': req.first_name,
            'Nom': req.last_name,
            'Pays': req.country,
            'Ville': req.city,
            'Adresse': req.address,
            'Téléphone': req.phone,
            'WhatsApp': req.whatsapp,
            'Message': req.message,
            'Date': req.created_at.strftime('%Y-%m-%d %H:%M'),
            'Traitée': 'Oui' if req.is_processed else 'Non'
        })
    
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Demandes')
    output.seek(0)
    
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name='demandes_clients.xlsx')

# -------------------------------
# Création des tables automatiquement
# -------------------------------
with app.app_context():
    db.create_all()
    print("✅ Base de données créée avec succès !")

# -------------------------------
# Lancement de l'application
# -------------------------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
