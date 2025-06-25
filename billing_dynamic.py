def calculate_invoice(user_order, product_data, discounts=None, overall_discount=0):
    """
    Enhanced invoice calculation with better error handling and validation.

    Args:
        user_order (dict): {product_name: quantity}
        product_data (list of dict): Parsed product records
        discounts (dict): Optional {product_name: discount_percent}
        overall_discount (float): Optional global discount on final amount

    Returns:
        dict: {
            "items": [ per-product details ],
            "summary": { overall totals }
        }
    """
    try:
        invoice_items = []
        subtotal = 0
        total_gst = 0
        total_installation = 0
        total_shipping = 0
        total_service = 0
        total_handling = 0
        
        # Ensure discounts is a dictionary
        if discounts is None:
            discounts = {}
        
        print(f"🧮 Calculating invoice for {len(user_order)} items...")
        
        for product_name, qty in user_order.items():
            # Find product with flexible matching
            product = find_product(product_data, product_name)
            
            if not product:
                print(f"⚠️ Product '{product_name}' not found in catalog")
                continue
            
            # Get base price with multiple field name support
            base_price = get_price(product)
            if base_price <= 0:
                print(f"⚠️ Invalid price for product '{product_name}': {base_price}")
                continue
            
            # Calculate discount
            discount_percent = discounts.get(product_name, 0)
            discounted_price = base_price * (1 - discount_percent / 100)
            
            # Calculate GST
            gst_rate = get_numeric_value(product, ['gst_rate', 'GST Rate', 'tax_rate'], 18)
            gst_amount = (discounted_price * gst_rate / 100) * qty
            total_gst += gst_amount
            
            # Calculate additional charges
            install = get_numeric_value(product, ['Installation Charge', 'installation_charge'], 0) * qty
            service = get_numeric_value(product, ['Service Charge', 'service_charge', 'service_fee'], 0) * qty
            shipping = get_numeric_value(product, ['Shipping Charge', 'shipping_charge'], 0) * qty
            handling = get_numeric_value(product, ['Handling Fee', 'handling_fee'], 0) * qty
            
            total_installation += install
            total_shipping += shipping
            total_service += service
            total_handling += handling
            
            # Calculate totals
            product_subtotal = discounted_price * qty
            line_total = product_subtotal + gst_amount + install + shipping + service + handling
            subtotal += product_subtotal
            
            # Check for recorded total (for discrepancy analysis)
            recorded_total = get_numeric_value(product, ['Total Price', 'total_price'], None)
            expected_total = recorded_total * qty if recorded_total else None
            discrepancy = round(expected_total - line_total, 2) if expected_total else None
            
            # Create invoice item
            invoice_item = {
                "name": product_name,
                "qty": qty,
                "unit_price": round(base_price, 2),
                "discount_percent": discount_percent,
                "discounted_price": round(discounted_price, 2),
                "gst_rate": gst_rate,
                "gst_amount": round(gst_amount, 2),
                "installation_charge": round(install, 2),
                "shipping_charge": round(shipping, 2),
                "service_charge": round(service, 2),
                "handling_fee": round(handling, 2),
                "calculated_total": round(line_total, 2)
            }
            
            # Add discrepancy info if available
            if expected_total is not None:
                invoice_item["recorded_total_price"] = round(expected_total, 2)
                invoice_item["discrepancy_vs_recorded"] = discrepancy
            
            invoice_items.append(invoice_item)
            
            print(f"  ✅ {product_name}: {qty}x @ ₹{base_price} = ₹{line_total:.2f}")
        
        # Calculate final totals
        total_before_discount = subtotal + total_gst + total_installation + total_shipping + total_service + total_handling
        discount_amount = total_before_discount * overall_discount / 100
        grand_total = total_before_discount - discount_amount
        
        # Create summary
        summary = {
            "subtotal": round(subtotal, 2),
            "total_gst": round(total_gst, 2),
            "total_installation": round(total_installation, 2),
            "total_shipping": round(total_shipping, 2),
            "total_service": round(total_service, 2),
            "total_handling": round(total_handling, 2),
            "overall_discount": round(discount_amount, 2),
            "grand_total": round(grand_total, 2)
        }
        
        result = {
            "items": invoice_items,
            "summary": summary
        }
        
        print(f"✅ Invoice calculated: ₹{grand_total:.2f} total for {len(invoice_items)} items")
        return result
        
    except Exception as e:
        print(f"❌ Error calculating invoice: {str(e)}")
        raise

def find_product(product_data, product_name):
    """
    Find product with flexible name matching
    """
    # Exact match first
    for product in product_data:
        if product.get("name", "").lower() == product_name.lower():
            return product
    
    # Check alternative name fields
    for product in product_data:
        alt_names = [
            product.get("Product Name", ""),
            product.get("product_name", ""),
            product.get("title", ""),
            product.get("description", "")
        ]
        if any(name.lower() == product_name.lower() for name in alt_names if name):
            return product
    
    # Partial match as last resort
    for product in product_data:
        product_names = [
            product.get("name", ""),
            product.get("Product Name", ""),
            product.get("product_name", "")
        ]
        if any(product_name.lower() in name.lower() for name in product_names if name):
            return product
    
    return None

def get_price(product):
    """
    Get price with multiple field name support
    """
    price_fields = ['price', 'base_price', 'Price', 'Base Price', 'rate', 'amount', 'cost']
    return get_numeric_value(product, price_fields, 0)

def get_numeric_value(product, field_names, default=0):
    """
    Get numeric value from product with multiple possible field names
    """
    for field in field_names:
        if field in product:
            try:
                value = float(product[field])
                if value >= 0:  # Ensure non-negative values
                    return value
            except (ValueError, TypeError):
                continue
    return default

def validate_product_data(product_data):
    """
    Validate product data structure and contents
    """
    if not isinstance(product_data, list):
        raise ValueError("Product data must be a list")
    
    if not product_data:
        raise ValueError("Product data is empty")
    
    required_fields = ['name']
    recommended_fields = ['price', 'base_price', 'gst_rate']
    
    issues = []
    
    for i, product in enumerate(product_data):
        if not isinstance(product, dict):
            issues.append(f"Product {i+1}: Not a dictionary")
            continue
        
        # Check required fields
        for field in required_fields:
            if field not in product or not product[field]:
                issues.append(f"Product {i+1}: Missing required field '{field}'")
        
        # Check recommended fields
        has_price = any(field in product for field in ['price', 'base_price', 'Price', 'Base Price'])
        if not has_price:
            issues.append(f"Product {i+1} ({product.get('name', 'Unknown')}): No price field found")
    
    if issues:
        print("⚠️ Product data validation issues:")
        for issue in issues[:10]:  # Show first 10 issues
            print(f"  - {issue}")
        if len(issues) > 10:
            print(f"  ... and {len(issues) - 10} more issues")
    else:
        print("✅ Product data validation passed")
    
    return len(issues) == 0

def format_currency(amount):
    """Format amount as Indian currency"""
    return f"₹{amount:,.2f}"

def generate_invoice_summary(invoice_data):
    """
    Generate a text summary of the invoice
    """
    items = invoice_data['items']
    summary = invoice_data['summary']
    
    lines = []
    lines.append("📋 INVOICE SUMMARY")
    lines.append("=" * 50)
    
    for item in items:
        lines.append(f"{item['name']}: {item['qty']}x @ {format_currency(item['unit_price'])} = {format_currency(item['calculated_total'])}")
        if item['discount_percent'] > 0:
            lines.append(f"  (Discount: {item['discount_percent']}%)")
    
    lines.append("-" * 50)
    lines.append(f"Subtotal: {format_currency(summary['subtotal'])}")
    lines.append(f"GST: {format_currency(summary['total_gst'])}")
    lines.append(f"Other Charges: {format_currency(summary['total_installation'] + summary['total_shipping'] + summary['total_service'] + summary['total_handling'])}")
    
    if summary['overall_discount'] > 0:
        lines.append(f"Overall Discount: -{format_currency(summary['overall_discount'])}")
    
    lines.append("=" * 50)
    lines.append(f"GRAND TOTAL: {format_currency(summary['grand_total'])}")
    
    return "\n".join(lines)

# Example usage and testing
if __name__ == "__main__":
    # Sample test data
    sample_products = [
        {
            "name": "Dome Camera HD",
            "price": 1500,
            "gst_rate": 18,
            "Installation Charge": 100,
            "Service Charge": 50,
            "Shipping Charge": 75,
            "Handling Fee": 25
        },
        {
            "name": "NVR Recorder 8-Channel",
            "price": 7000,
            "gst_rate": 18,
            "Installation Charge": 500,
            "Service Charge": 200,
            "Shipping Charge": 150,
            "Handling Fee": 50
        }
    ]
    
    sample_order = {
        "Dome Camera HD": 2,
        "NVR Recorder 8-Channel": 1
    }
    
    sample_discounts = {
        "Dome Camera HD": 10  # 10% discount
    }
    
    try:
        # Validate data
        validate_product_data(sample_products)
        
        # Calculate invoice
        invoice = calculate_invoice(
            user_order=sample_order,
            product_data=sample_products,
            discounts=sample_discounts,
            overall_discount=5  # 5% overall discount
        )
        
        # Print summary
        print("\n" + generate_invoice_summary(invoice))
        
    except Exception as e:
        print(f"❌ Test failed: {e}")