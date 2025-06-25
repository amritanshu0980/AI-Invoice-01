from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
import os
import json
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
import pandas as pd
import re
from jinja2 import Template

# Import your existing modules
from dynamic_parser import dynamic_parse_and_save, test_gemini_connection
from billing_dynamic import calculate_invoice, validate_product_data, generate_invoice_summary

# Import Gemini AI
import google.generativeai as genai
from dotenv import load_dotenv
import pdfkit

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['INVOICE_FOLDER'] = 'invoices'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['INVOICE_FOLDER'], exist_ok=True)
os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)

# Configure Gemini AI
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        GEMINI_AVAILABLE = True
        print("✅ Gemini AI configured successfully")
    except Exception as e:
        print(f"⚠️ Error configuring Gemini AI: {e}")
        GEMINI_AVAILABLE = False
        model = None
else:
    print("⚠️ GEMINI_API_KEY not found. Please set it in your .env file")
    GEMINI_AVAILABLE = False
    model = None

# Enhanced in-memory storage with persistent conversation history
session_data = {}

def get_session_data(session_id):
    """Get or create session data"""
    if session_id not in session_data:
        session_data[session_id] = {
            'cart': {},
            'client_details': {},
            'conversation_history': [],
            'products': [],
            'catalog_source': 'default',
            'overall_discount': 0  # ADDED: Overall discount tracking
        }
    return session_data[session_id]

def load_default_products():
    """Load products from product_data.json if it exists"""
    try:
        if os.path.exists('product_data.json'):
            with open('product_data.json', 'r') as f:
                products = json.load(f)
            print(f"✅ Loaded {len(products)} products from product_data.json")
            return products
        else:
            print("⚠️ product_data.json not found")
            return []
    except Exception as e:
        print(f"❌ Error loading product_data.json: {e}")
        return []

def parse_for_streamlit(file_path):
    """Parse file and return data directly for Flask integration"""
    try:
        products = dynamic_parse_and_save(file_path, output_path=None)
        return products
    except Exception as e:
        print(f"Error parsing for Flask: {e}")
        return []

# Load default products on startup
default_products = load_default_products()

@app.route('/')
def index():
    """Serve the chat interface"""
    return render_template('chat_interface.html')

@app.route('/api/status')
def status():
    """Check API and Gemini status"""
    try:
        gemini_status, gemini_message = test_gemini_connection()
    except:
        gemini_status, gemini_message = False, "Gemini connection test failed"
    
    return jsonify({
        'api_status': 'online',
        'gemini_status': 'online' if gemini_status else 'offline',
        'gemini_message': gemini_message,
        'default_products_count': len(default_products),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    """Smart natural language chat endpoint"""
    try:
        data = request.json
        user_message = data.get('message', '')
        session_id = data.get('session_id', request.headers.get('Session-ID', 'default'))
        
        if not user_message:
            return jsonify({'error': 'No message provided'}), 400
        
        print(f"💬 User message: {user_message}")
        
        session = get_session_data(session_id)
        
        # Get products (uploaded or default)
        if session['products']:
            products = session['products']
        else:
            products = default_products
            session['products'] = products
        
        # Process with enhanced natural language understanding
        response, action_data = process_natural_language(user_message, session, products)
        
        # Add to conversation history with proper context
        session['conversation_history'].append({
            'role': 'user',
            'content': user_message,
            'timestamp': datetime.now().isoformat()
        })
        session['conversation_history'].append({
            'role': 'assistant',
            'content': response,
            'timestamp': datetime.now().isoformat(),
            'action_data': action_data
        })
        
        # Keep last 20 messages for better context
        session['conversation_history'] = session['conversation_history'][-20:]
        
        return jsonify({
            'response': response,
            'action_data': action_data,
            'cart_count': len(session['cart']),
            'has_products': len(products) > 0,
            'product_count': len(products),
            'session_id': session_id,
            'overall_discount': session['overall_discount']  # ADDED: Include overall discount
        })
        
    except Exception as e:
        print(f"❌ Error processing chat: {str(e)}")
        return jsonify({'error': f'Error processing chat: {str(e)}'}), 500

def process_natural_language(message, session, products):
    """Enhanced natural language processing with better conversation understanding"""
    try:
        if not GEMINI_AVAILABLE or not model:
            return get_fallback_response(message, session, products)
        
        # Build rich context for conversation memory
        cart_summary = ""
        if session['cart']:
            cart_summary = "\n\nCURRENT CART CONTENTS:\n"
            cart_total = 0
            for item_id, item in session['cart'].items():
                discounted_price = item['unit_price'] * (1 - item['discount']/100)
                item_total = discounted_price * item['quantity']
                cart_total += item_total
                cart_summary += f"- {item['name']}: {item['quantity']} units @ ₹{item['unit_price']} each"
                if item['discount'] > 0:
                    cart_summary += f" (with {item['discount']}% discount = ₹{discounted_price:.2f} each)"
                cart_summary += f" = ₹{item_total:.2f}\n"
            
            # ADDED: Show overall discount in context
            if session['overall_discount'] > 0:
                overall_discount_amount = cart_total * session['overall_discount'] / 100
                cart_summary += f"\nOverall Cart Discount: {session['overall_discount']}% (₹{overall_discount_amount:.2f})"
                cart_summary += f"\nCart Total after Overall Discount: ₹{cart_total - overall_discount_amount:.2f}"
            else:
                cart_summary += f"\nCart Total: ₹{cart_total:.2f}"
        else:
            cart_summary = "\n\nCURRENT CART: Empty"
        
        # Build conversation context for memory
        conversation_context = ""
        if session['conversation_history']:
            conversation_context = "\n\nRECENT CONVERSATION HISTORY:\n"
            for msg in session['conversation_history'][-8:]:  # Last 8 messages for context
                role = "User" if msg['role'] == 'user' else "Assistant"
                conversation_context += f"{role}: {msg['content'][:150]}...\n"
        
        # Create product catalog summary
        product_catalog = ""
        if products:
            product_catalog = "\n\nAVAILABLE PRODUCTS:\n"
            for i, product in enumerate(products, 1):
                product_catalog += f"{i}. {product['name']} - ₹{product['price']:,.2f}\n"
        
        # Enhanced system prompt for natural conversation
        system_prompt = f"""
You are an intelligent AI shopping assistant helping customers manage their cart and create invoices. 

YOUR ROLE:
- Understand natural language requests about shopping, cart management, and invoicing
- Be conversational, helpful, and remember the context of our conversation
- Help customers find products, manage their cart, and generate invoices

CURRENT SITUATION:
- Available products: {len(products)}
- Items in cart: {len(session['cart'])}
- Overall cart discount: {session['overall_discount']}%
{cart_summary}
{conversation_context}
{product_catalog}

USER'S MESSAGE: "{message}"

INSTRUCTIONS FOR RESPONSES:
1. When user wants to ADD/BUY products:
   - Parse their request to extract: product name, quantity, discount
   - ONLY use POSITIVE quantities (never 0 or negative)
   - Respond naturally first, then add action code
   - Format: [ACTION:ADD|ProductName|Quantity|Discount]
   - Example: "I'll add 5 keyboards with 20% discount to your cart!"
             [ACTION:ADD|Professional Cable Tester|5|20]

2. When user wants to REMOVE products:
   - Parse their request to extract: product name, quantity
   - Format: [ACTION:REMOVE|ProductName|Quantity|0]

3. When user wants to APPLY DISCOUNT to existing cart items:
   - Parse requests like "add 10% discount to smart doorbell", "apply 15% off to cameras"
   - Format: [ACTION:APPLY_DISCOUNT|ProductName|DiscountPercent|0]

4. When user wants to UPDATE EXISTING items with discount:
   - If they want to change discount on existing item
   - Format: [ACTION:UPDATE_DISCOUNT|ProductName|NewDiscountPercent|0]

5. ADDED: When user wants to apply OVERALL CART DISCOUNT:
   - Parse requests like "add 50% discount to cart", "apply 25% overall discount", "give 10% discount on entire cart"
   - Format: [ACTION:OVERALL_DISCOUNT|||DiscountPercent]
   - Example: "I'll apply a 50% discount to your entire cart!"
             [ACTION:OVERALL_DISCOUNT|||50]

6. ADDED: When user wants to REMOVE OVERALL DISCOUNT:
   - Parse requests like "remove overall discount", "clear cart discount"
   - Format: [ACTION:CLEAR_OVERALL_DISCOUNT|||0]

7. When user wants to VIEW CART:
   - Format: [ACTION:SHOW_CART|||]

8. When user wants to see PRODUCTS:
   - Format: [ACTION:SHOW_PRODUCTS|||]

9. When user wants to GENERATE INVOICE:
   - Format: [ACTION:GENERATE_INVOICE|||]

10. When user wants DETAILED BREAKDOWN:
    - Parse requests like "show cart breakdown", "detailed pricing", "full breakdown"
    - Format: [ACTION:SHOW_BREAKDOWN|||]

11. For general conversation:
    - Just respond naturally, no action needed

IMPORTANT RULES:
- Always be conversational and helpful
- Remember our conversation history
- Use exact product names from the catalog
- If user mentions products not in catalog, suggest similar ones
- Be intelligent about quantity/discount parsing
- NEVER allow zero or negative quantities
- When adding products, confirm what you're doing
- For cart/product views, let the system handle formatting
- If user wants to apply discount to existing items, use APPLY_DISCOUNT action
- ADDED: For overall cart discounts, clearly explain the impact on total amount

EXAMPLES:
User: "I want 3 cameras with 10% off"
Response: "Perfect! I'll add 3 AI Security Camera 4K units to your cart with a 10% discount."
[ACTION:ADD|AI Security Camera 4K|3|10]

User: "add 5% discount to the smart doorbell in my cart"
Response: "I'll apply a 5% discount to the Smart Doorbell Pro Max in your cart."
[ACTION:APPLY_DISCOUNT|Smart Doorbell Pro Max|5|0]

User: "add 50% discount to the entire cart"
Response: "I'll apply a 50% overall discount to your entire cart! This will reduce your total bill significantly."
[ACTION:OVERALL_DISCOUNT|||50]

User: "remove the overall discount"
Response: "I'll remove the overall discount from your cart."
[ACTION:CLEAR_OVERALL_DISCOUNT|||0]

User: "what's in my cart?"
Response: "Let me show you what's currently in your cart."
[ACTION:SHOW_CART|||]

User: "remove 2 doorbells"
Response: "I'll remove 2 doorbells from your cart."
[ACTION:REMOVE|Smart Doorbell Pro Max|2|0]

User: "show cart breakdown"
Response: "Here's your detailed cart breakdown with all charges."
[ACTION:SHOW_BREAKDOWN|||]

Now respond to the user's message naturally and intelligently.
"""
        
        # Generate response with full context
        response = model.generate_content(system_prompt)
        response_text = response.text.strip()
        
        print(f"🤖 AI Response: {response_text}")
        
        # Extract action if present
        action_match = re.search(r'\[ACTION:([^|]+)\|([^|]*)\|([^|]*)\|([^|]*)\]', response_text)
        
        if action_match:
            action_type = action_match.group(1).strip()
            param1 = action_match.group(2).strip()
            param2 = action_match.group(3).strip()
            param3 = action_match.group(4).strip()
            
            print(f"✅ Action detected: {action_type} | {param1} | {param2} | {param3}")
            
            # Remove action from response text
            clean_response = re.sub(r'\[ACTION:[^\]]+\]', '', response_text).strip()
            
            # Process actions
            if action_type == "ADD":
                return execute_add_action(param1, param2, param3, session, products, clean_response)
            elif action_type == "REMOVE":
                return execute_remove_action(param1, param2, session, products, clean_response)
            elif action_type == "APPLY_DISCOUNT":
                return execute_apply_discount_action(param1, param2, session, clean_response)
            elif action_type == "UPDATE_DISCOUNT":
                return execute_update_discount_action(param1, param2, session, clean_response)
            elif action_type == "OVERALL_DISCOUNT":  # ADDED: Handle overall discount
                return execute_overall_discount_action(param3, session, clean_response)
            elif action_type == "CLEAR_OVERALL_DISCOUNT":  # ADDED: Handle clear overall discount
                return execute_clear_overall_discount_action(session, clean_response)
            elif action_type == "SHOW_CART":
                return show_cart_formatted(session), {"action": "show_cart"}
            elif action_type == "SHOW_PRODUCTS":
                return show_products_formatted(products), {"action": "show_products"}
            elif action_type == "GENERATE_INVOICE":
                return process_invoice_generation(session), {"action": "generate_invoice"}
            elif action_type == "SHOW_BREAKDOWN":
                return show_cart_detailed_breakdown(session), {"action": "show_cart_breakdown"}
        
        # Clean response of any remaining action markers
        clean_response = re.sub(r'\[ACTION:[^\]]+\]', '', response_text).strip()
        return clean_response, None
        
    except Exception as e:
        print(f"❌ Error in natural language processing: {str(e)}")
        return get_fallback_response(message, session, products)

# ADDED: Execute overall discount action
def execute_overall_discount_action(discount_str, session, ai_response):
    """Apply overall discount to entire cart"""
    try:
        try:
            discount = float(discount_str) if discount_str else 0
        except:
            discount = 0
        
        if discount < 0 or discount > 100:
            return f"❌ Invalid discount percentage. Please use a value between 0 and 100.", None
        
        if not session['cart']:
            return f"❌ Cannot apply overall discount - your cart is empty!<br><br>🛒 Add some products first.", None
        
        # Calculate current cart total
        cart_subtotal = 0
        for item_id, item in session['cart'].items():
            discounted_price = item['unit_price'] * (1 - item['discount']/100)
            item_total = discounted_price * item['quantity']
            cart_subtotal += item_total
        
        # Set overall discount
        old_discount = session['overall_discount']
        session['overall_discount'] = discount
        
        # Calculate discount amounts
        new_discount_amount = cart_subtotal * discount / 100
        new_total = cart_subtotal - new_discount_amount
        
        response_lines = [ai_response if ai_response else "✅ Overall cart discount applied!"]
        response_lines.extend([
            "",
            f"🛒 Cart Items: {len(session['cart'])} different products",
            f"💰 Cart Subtotal: ₹{cart_subtotal:,.2f}",
            f"🏷️ Overall Discount: {discount}%",
            f"💸 Discount Amount: ₹{new_discount_amount:,.2f}",
            f"💳 New Cart Total: ₹{new_total:,.2f}",
            "",
            "💡 This discount applies to the entire cart total",
            "📋 Say 'show cart breakdown' for detailed pricing",
            "🧾 Say 'generate invoice' to create final bill with all discounts"
        ])
        
        return "<br>".join(response_lines), {
            "action": "overall_discount",
            "discount": discount
        }
        
    except Exception as e:
        print(f"❌ Error applying overall discount: {str(e)}")
        return f"❌ Error applying overall discount: {str(e)}", None

# ADDED: Execute clear overall discount action
def execute_clear_overall_discount_action(session, ai_response):
    """Clear overall discount from cart"""
    try:
        if session['overall_discount'] == 0:
            return f"💡 No overall discount is currently applied to your cart.", None
        
        # Calculate current totals
        cart_subtotal = 0
        for item_id, item in session['cart'].items():
            discounted_price = item['unit_price'] * (1 - item['discount']/100)
            item_total = discounted_price * item['quantity']
            cart_subtotal += item_total
        
        old_discount = session['overall_discount']
        
        # Clear overall discount
        session['overall_discount'] = 0
        
        response_lines = [ai_response if ai_response else "✅ Overall discount removed!"]
        response_lines.extend([
            "",
            f"🛒 Cart Items: {len(session['cart'])} different products",
            f"🏷️ Overall Discount: {old_discount}% → 0%",
            f"💳 New Cart Total: ₹{cart_subtotal:,.2f}",
            "",
            "💡 Individual item discounts are still applied",
            "📋 Say 'show cart' to see updated totals"
        ])
        
        return "<br>".join(response_lines), {
            "action": "clear_overall_discount"
        }
        
    except Exception as e:
        print(f"❌ Error clearing overall discount: {str(e)}")
        return f"❌ Error clearing overall discount: {str(e)}", None

def execute_add_action(product_name, quantity_str, discount_str, session, products, ai_response):
    """Execute add to cart action with intelligent processing"""
    try:
        # Parse parameters
        try:
            quantity = int(quantity_str) if quantity_str and quantity_str.isdigit() else 1
        except:
            quantity = 1
            
        try:
            discount = float(discount_str) if discount_str else 0
        except:
            discount = 0
        
        # FIXED: Prevent zero or negative quantities
        if quantity <= 0:
            return f"❌ Cannot add zero or negative quantity products to cart.<br><br>💡 Please specify a positive quantity like 'add 2 {product_name}'", None
        
        print(f"🛍️ Adding: {product_name}, Qty: {quantity}, Discount: {discount}%")
        
        # Find product with smart matching
        product = smart_product_search(product_name, products)
        if not product:
            return f"❌ I couldn't find '{product_name}' in our catalog.<br><br>📋 Available products:<br>" + "<br>".join([f"• {p['name']}" for p in products[:10]]), None
        
        # FIXED: Use product name as primary key (not including discount)
        item_id = product['name']
        if item_id in session['cart']:
            # FIXED: Update existing item by adding quantity and updating discount
            existing_item = session['cart'][item_id]
            existing_item['quantity'] += quantity
            # If new discount is provided, update it
            if discount > 0:
                existing_item['discount'] = discount
            action_text = f"Updated existing cart item: +{quantity} units"
        else:
            # Create new cart item
            session['cart'][item_id] = {
                'name': product['name'],
                'unit_price': product['price'],
                'quantity': quantity,
                'discount': discount,
                'added_time': datetime.now().isoformat(),
                # Store additional charges for detailed breakdown
                'installation_charge': product.get('Installation Charge', 0),
                'service_charge': product.get('Service Charge', 0),
                'shipping_charge': product.get('Shipping Charge', 0),
                'handling_fee': product.get('Handling Fee', 0),
                'gst_rate': product.get('gst_rate', 18)
            }
            action_text = "Added new item to cart"
        
        # Calculate simplified total (base price + discount only)
        final_discount = session['cart'][item_id]['discount']
        discounted_price = product['price'] * (1 - final_discount/100)
        total_quantity = session['cart'][item_id]['quantity']
        simple_total = discounted_price * total_quantity
        
        # Create simplified response (like most e-commerce sites)
        response_lines = [ai_response if ai_response else "✅ Added to cart!"]
        response_lines.extend([
            "",
            f"📦 {product['name']}",
            f"🔢 Quantity: {total_quantity} units (added {quantity})",
            f"💰 Price: ₹{product['price']:,.2f} each"
        ])
        
        if final_discount > 0:
            response_lines.extend([
                f"🏷️ Discount: {final_discount}%",
                f"💸 Discounted Price: ₹{discounted_price:,.2f} each"
            ])
        
        response_lines.extend([
            f"💳 Item Total: ₹{simple_total:,.2f}",
            "",
            f"🛒 Cart now has {len(session['cart'])} different items"
        ])
        
        # ADDED: Show overall discount info if applied
        if session['overall_discount'] > 0:
            response_lines.extend([
                f"🏷️ Overall Cart Discount: {session['overall_discount']}% (applied at checkout)",
            ])
        
        response_lines.extend([
            "",
            "💡 Additional charges (installation, service, etc.) will be calculated in final invoice",
            "📋 Say 'show cart breakdown' for detailed pricing"
        ])
        
        return "<br>".join(response_lines), {
            "action": "add_to_cart",
            "product": product['name'],
            "quantity": quantity,
            "discount": final_discount
        }
        
    except Exception as e:
        print(f"❌ Error executing add action: {str(e)}")
        return f"❌ Error adding product: {str(e)}", None

def execute_apply_discount_action(product_name, discount_str, session, ai_response):
    """Apply discount to existing cart item"""
    try:
        try:
            discount = float(discount_str) if discount_str else 0
        except:
            discount = 0
        
        if discount < 0 or discount > 100:
            return f"❌ Invalid discount percentage. Please use a value between 0 and 100.", None
        
        # Find the cart item
        cart_item = None
        item_key = None
        
        # Search by exact name first
        for key, item in session['cart'].items():
            if product_name.lower() == item['name'].lower():
                cart_item = item
                item_key = key
                break
        
        # If not found, search by partial match
        if not cart_item:
            for key, item in session['cart'].items():
                if product_name.lower() in item['name'].lower():
                    cart_item = item
                    item_key = key
                    break
        
        if not cart_item:
            return f"❌ I couldn't find '{product_name}' in your cart.<br><br>🛒 Current cart items:<br>" + "<br>".join([f"• {item['name']}" for item in session['cart'].values()]), None
        
        # Update discount
        old_discount = cart_item['discount']
        cart_item['discount'] = discount
        
        # Calculate new totals
        discounted_price = cart_item['unit_price'] * (1 - discount/100)
        item_total = discounted_price * cart_item['quantity']
        
        response_lines = [ai_response if ai_response else "✅ Discount applied!"]
        response_lines.extend([
            "",
            f"📦 {cart_item['name']}",
            f"🏷️ Discount updated: {old_discount}% → {discount}%",
            f"💰 Original Price: ₹{cart_item['unit_price']:,.2f} each",
            f"💸 New Price: ₹{discounted_price:,.2f} each",
            f"🔢 Quantity: {cart_item['quantity']} units",
            f"💳 New Item Total: ₹{item_total:,.2f}",
            "",
            "📋 Say 'show cart' to see updated cart"
        ])
        
        return "<br>".join(response_lines), {
            "action": "apply_discount",
            "product": cart_item['name'],
            "discount": discount
        }
        
    except Exception as e:
        print(f"❌ Error applying discount: {str(e)}")
        return f"❌ Error applying discount: {str(e)}", None

def execute_update_discount_action(product_name, discount_str, session, ai_response):
    """Update discount for existing cart item (alias for apply_discount)"""
    return execute_apply_discount_action(product_name, discount_str, session, ai_response)

def execute_remove_action(product_name, quantity_str, session, products, ai_response):
    """Execute remove from cart action"""
    try:
        try:
            quantity = int(quantity_str) if quantity_str and quantity_str.isdigit() else 1
        except:
            quantity = 1
        
        # Find and remove from cart
        for item_id, item in list(session['cart'].items()):
            if product_name.lower() in item['name'].lower():
                if quantity >= item['quantity']:
                    del session['cart'][item_id]
                    return f"{ai_response}<br><br>✅ Removed all {item['name']} from cart<br>🛒 Cart now has {len(session['cart'])} items", {"action": "remove_from_cart"}
                else:
                    item['quantity'] -= quantity
                    return f"{ai_response}<br><br>✅ Removed {quantity}x {item['name']}<br>🔢 {item['quantity']} remaining<br>🛒 Cart has {len(session['cart'])} items", {"action": "remove_from_cart"}
        
        return f"{ai_response}<br><br>❌ Couldn't find '{product_name}' in your cart", None
        
    except Exception as e:
        return f"❌ Error removing product: {str(e)}", None

def show_cart_formatted(session):
    """Show cart with simple or detailed formatting based on request"""
    if not session['cart']:
        return "🛒 Your cart is empty<br><br>💡 Try adding some products! Say something like 'I want 2 cameras' or 'add 3 doorbells with 15% discount'"
    
    lines = [f"🛒 Your Shopping Cart ({len(session['cart'])} items)", ""]
    subtotal = 0
    
    for i, (item_id, item) in enumerate(session['cart'].items(), 1):
        discounted_price = item['unit_price'] * (1 - item['discount']/100)
        item_subtotal = discounted_price * item['quantity']
        subtotal += item_subtotal
        
        lines.append(f"{i}. {item['name']}")
        lines.append(f"   • Quantity: {item['quantity']} units")
        lines.append(f"   • Price: ₹{item['unit_price']:,.2f} each")
        
        if item['discount'] > 0:
            lines.append(f"   • Discount: {item['discount']}%")
            lines.append(f"   • Discounted Price: ₹{discounted_price:,.2f} each")
        
        lines.append(f"   • Subtotal: ₹{item_subtotal:,.2f}")
        lines.append("")
    
    # ADDED: Calculate and show overall discount
    overall_discount_amount = 0
    final_total = subtotal
    
    if session['overall_discount'] > 0:
        overall_discount_amount = subtotal * session['overall_discount'] / 100
        final_total = subtotal - overall_discount_amount
    
    lines.extend([
        f"💰 Cart Subtotal: ₹{subtotal:,.2f}"
    ])
    
    # ADDED: Show overall discount if applied
    if session['overall_discount'] > 0:
        lines.extend([
            f"🏷️ Overall Cart Discount ({session['overall_discount']}%): -₹{overall_discount_amount:,.2f}",
            f"💳 Cart Total after Discount: ₹{final_total:,.2f}"
        ])
    
    lines.extend([
        "",
        "💡 Additional charges (installation, service, GST, etc.) will be added during checkout",
        "",
        "🏷️ Say 'apply 10% discount to [product]' to add discounts to existing items",
        "🏷️ Say 'add 25% discount to cart' to apply overall discount to entire cart",
        "📋 Say 'show cart breakdown' for detailed pricing with all charges",
        "🧾 Say 'generate invoice' to create final bill with complete breakdown"
    ])
    
    return "<br>".join(lines)

def show_cart_detailed_breakdown(session):
    """Show cart with complete breakdown including all charges"""
    if not session['cart']:
        return "🛒 Your cart is empty<br><br>💡 Try adding some products first!"
    
    lines = [f"🛒 Detailed Cart Breakdown ({len(session['cart'])} items)", ""]
    
    subtotal = 0
    total_installation = 0
    total_service = 0
    total_shipping = 0
    total_handling = 0
    total_gst = 0
    grand_total = 0
    
    for i, (item_id, item) in enumerate(session['cart'].items(), 1):
        qty = item['quantity']
        base_price = item['unit_price']
        discount = item['discount']
        
        # Get additional charges
        installation = item.get('installation_charge', 0)
        service = item.get('service_charge', 0)
        shipping = item.get('shipping_charge', 0)
        handling = item.get('handling_fee', 0)
        gst_rate = item.get('gst_rate', 18)
        
        # Calculate prices
        discounted_price = base_price * (1 - discount/100)
        item_subtotal = discounted_price * qty
        
        # Calculate additional charges
        item_installation = installation * qty
        item_service = service * qty
        item_shipping = shipping * qty
        item_handling = handling * qty
        
        # Calculate GST on discounted price
        item_gst = (item_subtotal * gst_rate / 100)
        
        # Calculate total for this item
        item_total = item_subtotal + item_installation + item_service + item_shipping + item_handling + item_gst
        
        # Add to totals
        subtotal += item_subtotal
        total_installation += item_installation
        total_service += item_service
        total_shipping += item_shipping
        total_handling += item_handling
        total_gst += item_gst
        grand_total += item_total
        
        # Format item details
        lines.append(f"{i}. {item['name']}")
        lines.append(f"   📦 Quantity: {qty} units")
        lines.append(f"   💰 Base Price: ₹{base_price:,.2f} each")
        
        if discount > 0:
            lines.append(f"   🏷️ Discount: {discount}%")
            lines.append(f"   💸 Discounted Price: ₹{discounted_price:,.2f} each")
        
        lines.append(f"   📊 Price Breakdown:")
        lines.append(f"      • Product Subtotal: ₹{item_subtotal:,.2f}")
        
        if item_installation > 0:
            lines.append(f"      • Installation (₹{installation:,.2f} × {qty}): ₹{item_installation:,.2f}")
        if item_service > 0:
            lines.append(f"      • Service (₹{service:,.2f} × {qty}): ₹{item_service:,.2f}")
        if item_shipping > 0:
            lines.append(f"      • Shipping (₹{shipping:,.2f} × {qty}): ₹{item_shipping:,.2f}")
        if item_handling > 0:
            lines.append(f"      • Handling (₹{handling:,.2f} × {qty}): ₹{item_handling:,.2f}")
        
        lines.append(f"      • GST ({gst_rate}%): ₹{item_gst:,.2f}")
        lines.append(f"   💳 **Item Total: ₹{item_total:,.2f}**")
        lines.append("")
    
    # Overall totals before overall discount
    lines.extend([
        "📊 CART SUMMARY:",
        f"   • Products Subtotal: ₹{subtotal:,.2f}",
    ])
    
    if total_installation > 0:
        lines.append(f"   • Total Installation: ₹{total_installation:,.2f}")
    if total_service > 0:
        lines.append(f"   • Total Service: ₹{total_service:,.2f}")
    if total_shipping > 0:
        lines.append(f"   • Total Shipping: ₹{total_shipping:,.2f}")
    if total_handling > 0:
        lines.append(f"   • Total Handling: ₹{total_handling:,.2f}")
    
    lines.extend([
        f"   • Total GST: ₹{total_gst:,.2f}",
        "",
        f"💰 SUBTOTAL: ₹{grand_total:,.2f}"
    ])
    
    # ADDED: Apply overall discount if set
    final_total = grand_total
    if session['overall_discount'] > 0:
        overall_discount_amount = grand_total * session['overall_discount'] / 100
        final_total = grand_total - overall_discount_amount
        
        lines.extend([
            f"🏷️ Overall Cart Discount ({session['overall_discount']}%): -₹{overall_discount_amount:,.2f}",
            "",
            f"💰 GRAND TOTAL: ₹{final_total:,.2f}"
        ])
    else:
        lines.extend([
            "",
            f"💰 GRAND TOTAL: ₹{final_total:,.2f}"
        ])
    
    lines.extend([
        "",
        "💡 This matches what you'll see in your final invoice",
        "🏷️ Say 'add X% discount to cart' to apply overall discount",
        "🧾 Say 'generate invoice' to create the official document"
    ])
    
    return "<br>".join(lines)

def show_products_formatted(products):
    """Show products with proper formatting and pagination"""
    if not products:
        return "📋 No products available. Please upload a catalog."
    
    lines = [f"📋 Product Catalog ({len(products)} items)", ""]
    
    # Show ALL products (fixed the issue)
    for i, product in enumerate(products, 1):
        lines.append(f"{i:2d}. {product['name']} - ₹{product['price']:,.2f}")
    
    lines.extend([
        "",
        "💡 To add products, just tell me naturally:",
        "• 'I want 3 cameras with 10% discount'",
        "• 'Add 5 doorbells to my cart'",
        "• 'Buy 2 Smart TVs'",
        "",
        "🏷️ To add discounts to cart items:",
        "• 'Apply 10% discount to smart doorbell'",
        "• 'Add 15% off to the cameras in my cart'",
        "• 'Add 50% discount to cart' for overall discount"
    ])
    
    return "<br>".join(lines)

def process_invoice_generation(session):
    """Process invoice generation request"""
    if not session['cart']:
        return "❌ Cannot generate invoice - your cart is empty!<br><br>🛒 Add some products first, then I can create your invoice."
    
    lines = [
        "🔄 Generating your invoice...",
        "",
        f"📋 Processing {len(session['cart'])} different products",
        "💰 Calculating totals with discounts and taxes",
        "📄 Creating professional invoice document",
        "📥 Download will be available shortly"
    ]
    
    return "<br>".join(lines)

def smart_product_search(search_term, products):
    """Smart product search with multiple matching strategies and suggestions"""
    if not search_term:
        return None
    
    search_lower = search_term.lower()
    
    # Strategy 1: Exact match
    for product in products:
        if product['name'].lower() == search_lower:
            return product
    
    # Strategy 2: Contains match
    for product in products:
        if search_lower in product['name'].lower():
            return product
    
    # Strategy 3: Word matching
    search_words = search_lower.split()
    for product in products:
        product_words = product['name'].lower().split()
        if any(word in product_words for word in search_words if len(word) > 2):
            return product
    
    # Strategy 4: Partial word matching
    for product in products:
        product_name = product['name'].lower()
        for word in search_words:
            if len(word) > 3 and word in product_name:
                return product
    
    return None

def get_fallback_response(message, session, products):
    """Fallback response when AI is not available"""
    message_lower = message.lower()
    
    if any(word in message_lower for word in ['cart', 'basket']):
        return show_cart_formatted(session), {"action": "show_cart"}
    elif any(word in message_lower for word in ['products', 'catalog', 'list']):
        return show_products_formatted(products), {"action": "show_products"}
    elif any(word in message_lower for word in ['invoice', 'bill', 'checkout']):
        return process_invoice_generation(session), {"action": "generate_invoice"}
    else:
        return "💬 I can help you shop, manage your cart, and create invoices. Try asking me to show products or add items to your cart!", None

@app.route('/api/generate_invoice_from_cart', methods=['POST'])
def generate_invoice_from_cart():
    """Generate invoice from cart contents with overall discount support"""
    try:
        data = request.json
        session_id = data.get('session_id', request.headers.get('Session-ID', 'default'))
        
        session = get_session_data(session_id)
        
        if not session['cart']:
            return jsonify({'error': 'Cart is empty'}), 400
        
        # Convert cart to order format for billing system
        order = {}
        discounts = {}
        
        for item_id, item in session['cart'].items():
            product_name = item['name']
            order[product_name] = item['quantity']
            if item['discount'] > 0:
                discounts[product_name] = item['discount']
        
        # Get products
        products = session['products'] if session['products'] else default_products
        
        # ADDED: Pass overall discount to billing system
        overall_discount = session.get('overall_discount', 0)
        
        # Calculate invoice using your billing_dynamic.py with overall discount
        invoice = calculate_invoice(
            user_order=order,
            product_data=products,
            discounts=discounts,
            overall_discount=overall_discount  # ADDED: Pass overall discount
        )
        
        # Generate PDF invoice using pdfkit
        pdf_path = generate_invoice_pdf(invoice, session['client_details'], session_id)
        
        invoice_number = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Clear cart and overall discount after successful invoice generation
        session['cart'] = {}
        session['overall_discount'] = 0  # ADDED: Reset overall discount
        
        return jsonify({
            'success': True,
            'invoice': invoice,
            'pdf_path': pdf_path,
            'invoice_number': invoice_number,
            'message': 'PDF invoice generated successfully and cart cleared!'
        })
        
    except Exception as e:
        print(f"❌ Error generating invoice: {str(e)}")
        return jsonify({'error': f'Error generating invoice: {str(e)}'}), 500

def generate_invoice_pdf(invoice, client_details, session_id):
    """Generate PDF invoice using pdfkit and your invoice_template.html"""
    try:
        # Load your invoice template
        with open('invoice_template.html', 'r') as f:
            template_content = f.read()
        
        template = Template(template_content)
        
        # Prepare data for template
        seller = {
            'name': 'Zencia AI',
            'address': 'Sachivalaya Metro Station, Lucknow Uttar Pradesh 226001',
            'phone': '1234567890',
            'gstin': '14556789012345',
        }
        
        client = {
            'name': client_details.get('name', 'Walk-in Customer'),
            'address': client_details.get('address', 'N/A'),
            'gst_number': client_details.get('gst_number', 'N/A'),
            'place_of_supply': client_details.get('place_of_supply', 'N/A')
        }
        
        invoice_number = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        invoice_date = datetime.now().strftime('%d/%m/%Y')
        
        # Render HTML using your template
        html_content = template.render(
            invoice=invoice,
            seller=seller,
            client=client,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            supplier_ref='',
            other_ref='',
            amount_in_words=number_to_words(invoice['summary']['grand_total']),
            tax_in_words=number_to_words(invoice['summary']['total_gst'])
        )
        
        # Configure pdfkit options for better PDF generation
        options = {
            'page-size': 'A4',
            'margin-top': '0.5in',
            'margin-right': '0.5in',
            'margin-bottom': '0.5in',
            'margin-left': '0.5in',
            'encoding': "UTF-8",
            'no-outline': None,
            'enable-local-file-access': None,
            'print-media-type': None
        }
        
        # Generate PDF filename
        pdf_filename = f"invoice_{invoice_number}.pdf"
        pdf_path = os.path.join(app.config['INVOICE_FOLDER'], pdf_filename)
        
        # Convert HTML to PDF using pdfkit
        try:
            pdfkit.from_string(html_content, pdf_path, options=options)
            print(f"✅ PDF generated successfully: {pdf_filename}")
            return pdf_filename
        except Exception as pdf_error:
            print(f"❌ PDF generation error: {pdf_error}")
            # Fallback: Try without options if pdfkit fails
            try:
                pdfkit.from_string(html_content, pdf_path)
                print(f"✅ PDF generated (fallback mode): {pdf_filename}")
                return pdf_filename
            except Exception as fallback_error:
                print(f"❌ PDF fallback failed: {fallback_error}")
                # Final fallback: Generate HTML file
                html_filename = f"invoice_{invoice_number}.html"
                html_path = os.path.join(app.config['INVOICE_FOLDER'], html_filename)
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                print(f"⚠️ Generated HTML instead of PDF: {html_filename}")
                return html_filename
        
    except Exception as e:
        print(f"❌ Error generating invoice: {str(e)}")
        return None

def number_to_words(number):
    """Convert number to words"""
    try:
        from num2words import num2words
        return num2words(int(number), lang='en').title() + " Rupees Only"
    except ImportError:
        return f"Rupees {int(number)} Only"

@app.route('/api/download_invoice/<filename>')
def download_invoice(filename):
    """Download generated PDF or HTML invoice"""
    try:
        file_path = os.path.join(app.config['INVOICE_FOLDER'], filename)
        if os.path.exists(file_path):
            # Determine mimetype based on file extension
            if filename.endswith('.pdf'):
                mimetype = 'application/pdf'
            else:
                mimetype = 'text/html'
            
            return send_file(file_path, as_attachment=True, download_name=filename, mimetype=mimetype)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Error downloading file: {str(e)}'}), 500

@app.route('/api/client/save', methods=['POST'])
def save_client_details():
    """Save client details"""
    try:
        data = request.json
        session_id = data.get('session_id', request.headers.get('Session-ID', 'default'))
        
        session = get_session_data(session_id)
        session['client_details'] = {
            'name': data.get('name', ''),
            'address': data.get('address', ''),
            'gst_number': data.get('gst_number', ''),
            'place_of_supply': data.get('place_of_supply', ''),
            'phone': data.get('phone', ''),
            'email': data.get('email', ''),
            'saved_time': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'message': 'Client details saved successfully'
        })
        
    except Exception as e:
        return jsonify({'error': f'Error saving client details: {str(e)}'}), 500

@app.route('/api/client/get', methods=['GET'])
def get_client_details():
    """Get client details"""
    try:
        session_id = request.headers.get('Session-ID', 'default')
        session = get_session_data(session_id)
        
        return jsonify({
            'client': session['client_details']
        })
        
    except Exception as e:
        return jsonify({'error': f'Error getting client details: {str(e)}'}), 500

@app.route('/api/get_products', methods=['GET'])
def get_products():
    """Get all products for current session"""
    try:
        session_id = request.headers.get('Session-ID', 'default')
        session = get_session_data(session_id)
        
        # Get products (uploaded or default)
        if session['products']:
            products = session['products']
            source = session['catalog_source']
            filename = 'uploaded_catalog'
        else:
            products = default_products
            session['products'] = products
            source = 'default'
            filename = 'product_data.json'
        
        return jsonify({
            'products': products,
            'count': len(products),
            'filename': filename,
            'source': source
        })
        
    except Exception as e:
        return jsonify({'error': f'Error getting products: {str(e)}'}), 500

@app.route('/api/upload_catalog', methods=['POST'])
def upload_catalog():
    """Handle catalog file uploads"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        session_id = request.headers.get('Session-ID', str(uuid.uuid4()))
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Process file using your dynamic parser
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_filename)
        file.save(file_path)
        
        # Parse using your dynamic_parser.py
        products = parse_for_streamlit(file_path)
        
        if not validate_product_data(products):
            os.remove(file_path)
            return jsonify({'error': 'Invalid product data structure'}), 400
        
        # Update session data
        session = get_session_data(session_id)
        session['products'] = products
        session['catalog_source'] = 'uploaded'
        
        # Clean up
        os.remove(file_path)
        
        return jsonify({
            'success': True,
            'message': f'Successfully parsed {len(products)} products',
            'product_count': len(products),
            'filename': filename,
            'session_id': session_id
        })
        
    except Exception as e:
        print(f"❌ Error processing file: {str(e)}")
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

if __name__ == '__main__':
    print("🚀 Starting Smart Natural Language AI Invoice Assistant...")
    print(f"📁 Upload folder: {app.config['UPLOAD_FOLDER']}")
    print(f"📄 Invoice folder: {app.config['INVOICE_FOLDER']}")
    print(f"🤖 Gemini AI: {'Available' if GEMINI_AVAILABLE else 'Not Available'}")
    print(f"📦 Default products: {len(default_products)} loaded from product_data.json")
    print(f"🏷️ Overall discount functionality: Added")
    
    # Create required directories
    for folder in ['templates', 'uploads', 'invoices']:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"📁 Created {folder}/ directory")
    
    app.run(debug=True, host='0.0.0.0', port=5000)