import pandas as pd
import os
import json
import re

# Try to import and configure Gemini AI
try:
    import google.generativeai as genai
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Configure API key securely
    api_key = os.getenv("GEMINI_API_KEY")
    
    if api_key:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        GEMINI_AVAILABLE = True
        print("✅ Gemini AI configured successfully")
    else:
        print("⚠️ GEMINI_API_KEY not found in environment variables")
        GEMINI_AVAILABLE = False
        model = None
        
except ImportError as e:
    print(f"⚠️ Could not import required packages: {e}")
    GEMINI_AVAILABLE = False
    model = None
except Exception as e:
    print(f"⚠️ Error configuring Gemini AI: {e}")
    GEMINI_AVAILABLE = False
    model = None

def normalize_column(col):
    """Normalize column names to lowercase with underscores"""
    return col.strip().lower().replace(" ", "_").replace("-", "_")

def gemini_classify_column(column):
    """Use Gemini AI to classify column purpose"""
    if not GEMINI_AVAILABLE or not model:
        print(f"Gemini AI not available, using rule-based classification for: {column}")
        return fallback_classify_column(column)
    
    prompt = f"""
You are interpreting columns from a product catalog. What does the column "{column}" most likely represent?

Respond with ONLY ONE of these exact labels:
- name (for product names/descriptions)
- price (for base prices/rates)
- gst_rate (for tax rates)
- installation_charge (for installation fees)
- service_charge (for service fees)
- shipping_charge (for delivery costs)
- handling_fee (for processing fees)
- irrelevant (for unimportant data)

Return just the label, nothing else.
"""
    try:
        response = model.generate_content(prompt)
        label = response.text.strip().lower()
        # Clean the response
        label = re.sub(r"[^\w_]", "", label)
        return label
    except Exception as e:
        print(f"AI classification failed for '{column}': {e}")
        return fallback_classify_column(column)

def fallback_classify_column(column):
    """Rule-based column classification when AI is not available"""
    col_lower = column.lower()
    
    # Name patterns - be very specific to avoid Product ID confusion
    if any(word in col_lower for word in ['product_name', 'item_name', 'description', 'title']):
        return 'name'
    elif col_lower == 'name':
        return 'name'
    
    # Price patterns
    elif any(word in col_lower for word in ['base_price', 'price', 'cost', 'rate', 'amount', 'value']):
        return 'price'
    
    # GST patterns
    elif any(word in col_lower for word in ['gst', 'tax', 'vat']):
        return 'gst_rate'
    
    # Installation patterns
    elif any(word in col_lower for word in ['install', 'setup']):
        return 'installation_charge'
    
    # Service patterns
    elif any(word in col_lower for word in ['service', 'maintenance']):
        return 'service_charge'
    
    # Shipping patterns
    elif any(word in col_lower for word in ['shipping', 'delivery', 'freight']):
        return 'shipping_charge'
    
    # Handling patterns
    elif any(word in col_lower for word in ['handling', 'processing', 'admin']):
        return 'handling_fee'
    
    else:
        return 'irrelevant'

def enhanced_column_mapping(df):
    """Enhanced column mapping with FIXED priority for product names"""
    original_columns = df.columns.tolist()
    df.columns = [normalize_column(col) for col in df.columns]
    
    mapped_columns = {}
    used_labels = set()
    
    print("🔍 Column mapping process:")
    print(f"Original columns: {original_columns}")
    print(f"Normalized columns: {list(df.columns)}")
    
    # FIXED: Define rule-based mapping with SPECIFIC priority order
    mapping_rules = {
        'name': [
            'product_name',      # This should match first (Product Name)
            'item_name', 
            'description', 
            'title',
            'name'              # Generic 'name' comes last
            # Removed 'product' to avoid matching 'product_id'
        ],
        'price': ['base_price', 'price', 'rate', 'unit_price', 'amount', 'cost'],
        'gst_rate': ['gst_rate', 'gst', 'tax_rate', 'vat', 'tax'],
        'installation_charge': ['installation_charge', 'install', 'setup_fee', 'installation'],
        'service_charge': ['service_charge', 'service_fee', 'maintenance', 'service'],
        'shipping_charge': ['shipping_charge', 'delivery', 'freight', 'shipping'],
        'handling_fee': ['handling_fee', 'processing_fee', 'admin_fee', 'handling']
    }
    
    # Apply rule-based mapping with exact matching first
    for col in df.columns:
        mapped = False
        print(f"\n📋 Processing column: '{col}'")
        
        # Check for exact matches first
        for standard_name, variations in mapping_rules.items():
            if col in variations:
                if standard_name not in used_labels:
                    mapped_columns[col] = standard_name
                    used_labels.add(standard_name)
                    mapped = True
                    print(f"   ✅ Exact match: '{col}' → '{standard_name}'")
                    break
        
        # If no exact match, try partial matching
        if not mapped:
            for standard_name, variations in mapping_rules.items():
                if any(var in col.lower() for var in variations):
                    if standard_name not in used_labels:
                        mapped_columns[col] = standard_name
                        used_labels.add(standard_name)
                        mapped = True
                        print(f"   ✅ Partial match: '{col}' → '{standard_name}'")
                        break
        
        # Use AI classification (or fallback) if no rule matches
        if not mapped:
            try:
                label = gemini_classify_column(col)
                if label in mapping_rules.keys() and label not in used_labels:
                    mapped_columns[col] = label
                    used_labels.add(label)
                    print(f"   ✅ AI/Fallback: '{col}' → '{label}'")
                else:
                    # Handle duplicates or unknown labels
                    if label in used_labels:
                        final_label = f"{label}_{col}"
                    else:
                        final_label = label
                    mapped_columns[col] = final_label
                    used_labels.add(final_label)
                    print(f"   ⚠️ Fallback: '{col}' → '{final_label}'")
            except Exception:
                mapped_columns[col] = col
                print(f"   ❌ Error: '{col}' → '{col}' (unchanged)")
    
    return mapped_columns

def dynamic_parse_and_save(file_path, output_path="product_data.json"):
    """
    Enhanced dynamic parser with FIXED field mapping and standardization
    """
    try:
        # Determine file type and read
        ext = os.path.splitext(file_path)[-1].lower()
        if ext == ".xlsx":
            df = pd.read_excel(file_path)
        elif ext == ".csv":
            df = pd.read_csv(file_path)
        else:
            raise ValueError("Unsupported format. Please use CSV or Excel files.")
        
        print(f"📊 Processing {len(df)} rows from {file_path}")
        
        # Apply enhanced column mapping
        mapped_columns = enhanced_column_mapping(df)
        df = df.rename(columns=mapped_columns)
        
        # Convert numeric columns with better error handling
        for col in df.columns:
            if col != "name":
                try:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                except Exception:
                    continue
        
        # Convert to records
        product_data = df.to_dict(orient="records")
        
        # Standardize output format for billing compatibility
        standardized_products = []
        for product in product_data:
            # Create standardized product record
            standardized = {
                'name': str(product.get('name', 'Unknown Product')),
                'price': float(product.get('price', product.get('base_price', 0))),
                'gst_rate': float(product.get('gst_rate', 18)),
                'Installation Charge': float(product.get('installation_charge', 0)),
                'Service Charge': float(product.get('service_charge', product.get('service_fee', 0))),
                'Shipping Charge': float(product.get('shipping_charge', 0)),
                'Handling Fee': float(product.get('handling_fee', 0))
            }
            
            # Add any additional fields that were mapped
            for key, value in product.items():
                if key not in standardized and not key.startswith('irrelevant'):
                    standardized[key] = value
            
            standardized_products.append(standardized)
        
        # Save to JSON file only if output_path is provided
        if output_path:
            with open(output_path, "w") as f:
                json.dump(standardized_products, f, indent=2)
            print(f"✅ Saved {len(standardized_products)} products to {output_path}")
        
        print("\n🧠 Final Column Mappings:")
        for orig, new in mapped_columns.items():
            print(f"  - {orig} → {new}")
        
        # Show sample products to verify
        print(f"\n📋 Sample Product (first 3):")
        for i, product in enumerate(standardized_products[:3]):
            print(f"  Product {i+1}: {product.get('name', 'NO NAME')} - ₹{product.get('price', 0)}")
        
        # Show AI availability status
        if GEMINI_AVAILABLE:
            print("✅ Used Gemini AI for intelligent column classification")
        else:
            print("⚠️ Used rule-based classification (Gemini AI not available)")
        
        return standardized_products
        
    except Exception as e:
        print(f"❌ Error in dynamic parser: {str(e)}")
        raise

def parse_for_streamlit(file_path):
    """
    Parse file and return data directly for Streamlit integration
    """
    try:
        products = dynamic_parse_and_save(file_path, output_path=None)
        return products
    except Exception as e:
        print(f"Error parsing for Streamlit: {e}")
        return []

# Test connectivity
def test_gemini_connection():
    """Test if Gemini AI is properly configured"""
    if not GEMINI_AVAILABLE:
        return False, "Gemini AI not available - check API key and dependencies"
    
    try:
        test_response = model.generate_content("Test connection")
        return True, "Gemini AI connection successful"
    except Exception as e:
        return False, f"Gemini AI connection failed: {e}"

# Example usage
if __name__ == "__main__":
    # Test Gemini connection first
    connected, message = test_gemini_connection()
    print(message)
    
    # Test with your product catalog
    try:
        result = dynamic_parse_and_save("product_catalog.csv")
        print(f"\n🎉 Successfully processed {len(result)} products!")
        
        # Show sample product
        if result:
            print("\n📋 Sample Product:")
            sample = result[0]
            for key, value in sample.items():
                print(f"  {key}: {value}")
                
    except FileNotFoundError:
        print("❌ product_catalog.csv not found in current directory")
    except Exception as e:
        print(f"❌ Failed to process file: {e}")