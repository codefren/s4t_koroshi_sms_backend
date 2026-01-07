import requests

# Test the API endpoint
try:
    response = requests.get("http://localhost:8000/api/v1/items/")
    if response.status_code == 200:
        items = response.json()
        print(f"✓ Success! Found {len(items)} items")
        if items:
            print("\nFirst item:")
            first_item = items[0]
            print(f"  EAN: {first_item.get('ean')}")
            print(f"  Articulo: {first_item.get('articulo')}")
            print(f"  Cantidad: {first_item.get('cantidad')}")
    else:
        print(f"✗ Error: Status code {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"✗ Error: {e}")
