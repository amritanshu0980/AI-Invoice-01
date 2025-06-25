# This file has been updated to include comprehensive invoice calculations, discounts, and charges.

def calculate_invoice(user_order, product_data, discounts=None, overall_discount=0):
    """
    Calculate comprehensive invoice with all charges and discounts
    """
    if discounts is None:
        discounts = {}
    
    items = []
    subtotal = 0
    total_installation = 0
    total_service = 0
    total_shipping = 0
    total_handling = 0
    total_gst = 0
    
    # Process each item in the order
    for product_name, quantity in user_order.items():
        # Find the product in the catalog
        product = None
        for p in product_data:
            if p["name"] == product_name:
                product = p
                break
        
        if not product:
            continue
        
        # Get base price and discount
        unit_price = product.get("price", 0)
        discount = discounts.get(product_name, 0)
        
        # Calculate discounted price
        discounted_price = unit_price * (1 - discount/100)
        item_subtotal = discounted_price * quantity
        
        # Get additional charges
        installation_charge = product.get("Installation Charge", 0) * quantity
        service_charge = product.get("Service Charge", 0) * quantity
        shipping_charge = product.get("Shipping Charge", 0) * quantity
        handling_fee = product.get("Handling Fee", 0) * quantity
        
        # Calculate GST
        gst_rate = product.get("gst_rate", 18)
        total_before_gst = item_subtotal + installation_charge + service_charge + shipping_charge + handling_fee
        item_gst = total_before_gst * gst_rate / 100
        
        # Calculate total amount for this item
        total_amount = total_before_gst + item_gst
        
        # Create item object
        item = {
            "name": product_name,
            "qty": quantity,
            "unit_price": unit_price,
            "discount": discount,
            "discounted_price": discounted_price,
            "installation_charge": installation_charge,
            "service_charge": service_charge,
            "shipping_charge": shipping_charge,
            "handling_fee": handling_fee,
            "gst_rate": gst_rate,
            "item_gst": item_gst,
            "total_amount": total_amount
        }
        
        items.append(item)
        
        # Add to totals
        subtotal += item_subtotal
        total_installation += installation_charge
        total_service += service_charge
        total_shipping += shipping_charge
        total_handling += handling_fee
        total_gst += item_gst
    
    # Calculate totals
    total_ex_gst = subtotal + total_installation + total_service + total_shipping + total_handling
    total_incl_gst = total_ex_gst + total_gst
    
    # Apply overall discount
    overall_discount_amount = 0
    if overall_discount > 0:
        overall_discount_amount = total_incl_gst * overall_discount / 100
    
    grand_total = total_incl_gst - overall_discount_amount
    
    # Create invoice summary
    summary = {
        "subtotal": subtotal,
        "total_installation": total_installation,
        "total_service": total_service,
        "total_shipping": total_shipping,
        "total_handling": total_handling,
        "total_ex_gst": total_ex_gst,
        "gst_rate": 18,  # Default GST rate
        "total_gst": total_gst,
        "total_incl_gst": total_incl_gst,
        "overall_discount": overall_discount,
        "overall_discount_amount": overall_discount_amount,
        "grand_total": grand_total
    }
    
    return {
        "items": items,
        "summary": summary
    }

def validate_product_data(product_data):
    """
    Validate product data structure
    """
    if not isinstance(product_data, list):
        return False
    
    for product in product_data:
        if not isinstance(product, dict):
            return False
        if "name" not in product or "price" not in product:
            return False
    
    return True

def generate_invoice_summary(invoice):
    """
    Generate a text summary of the invoice
    """
    summary_lines = []
    summary_lines.append("Invoice Summary:")
    summary_lines.append(f"Items: {len(invoice['items'])}")
    summary_lines.append(f"Subtotal: ₹{invoice['summary']['subtotal']:,.2f}")
    
    if invoice["summary"]["total_installation"] > 0:
        summary_lines.append(f"Installation: ₹{invoice['summary']['total_installation']:,.2f}")
    if invoice["summary"]["total_service"] > 0:
        summary_lines.append(f"Service: ₹{invoice['summary']['total_service']:,.2f}")
    if invoice["summary"]["total_shipping"] > 0:
        summary_lines.append(f"Shipping: ₹{invoice['summary']['total_shipping']:,.2f}")
    if invoice["summary"]["total_handling"] > 0:
        summary_lines.append(f"Handling: ₹{invoice['summary']['total_handling']:,.2f}")
    
    summary_lines.append(f"GST ({invoice['summary']['gst_rate']}%): ₹{invoice['summary']['total_gst']:,.2f}")
    
    if invoice["summary"]["overall_discount"] > 0:
        summary_lines.append(f"Overall Discount ({invoice['summary']['overall_discount']}%): -₹{invoice['summary']['overall_discount_amount']:,.2f}")
    
    summary_lines.append(f"Grand Total: ₹{invoice['summary']['grand_total']:,.2f}")
    
    return "\n".join(summary_lines)

