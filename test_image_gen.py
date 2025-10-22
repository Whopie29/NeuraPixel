import requests
import os
from datetime import datetime
import hashlib

def test_image_generation():
    # Image details
    prompt = "a chocolate tree"
    width = 1024
    height = 1024
    seed = 42
    model = "flux"
    
    # Build Pollinations URL
    image_url = f"https://pollinations.ai/p/{prompt}?width={width}&height={height}&seed={seed}&model={model}"
    
    print(f"Generated URL: {image_url}")
    
    # Download image
    print("Downloading image...")
    response = requests.get(image_url)
    
    print(f"Response status: {response.status_code}")
    print(f"Content type: {response.headers.get('content-type')}")
    print(f"Content length: {len(response.content)} bytes")
    
    # Save image
    os.makedirs('generated_images', exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
    filename = f"{timestamp}_{prompt_hash}.jpg"
    filepath = os.path.join('generated_images', filename)
    
    with open(filepath, 'wb') as file:
        file.write(response.content)
    
    print(f"Image saved as: {filepath}")
    print("Download Completed")

if __name__ == "__main__":
    test_image_generation()