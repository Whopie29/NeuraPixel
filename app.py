from flask import Flask, render_template, request, jsonify, send_file
import os
import sys
import logging
import html
import re

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.image_generator import ImageGenerationService
from services.file_manager import FileManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InputValidator:
    """Comprehensive input validation and sanitization for the AI image generator."""
    
    # Potentially harmful patterns to filter out
    HARMFUL_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',               # JavaScript URLs
        r'on\w+\s*=',                # Event handlers
        r'<iframe[^>]*>.*?</iframe>', # Iframes
        r'<object[^>]*>.*?</object>', # Objects
        r'<embed[^>]*>.*?</embed>',   # Embeds
    ]
    
    # Inappropriate content keywords (basic filtering)
    INAPPROPRIATE_KEYWORDS = [
        'explicit', 'nsfw', 'nude', 'naked', 'sexual', 'porn', 'xxx',
        'violence', 'gore', 'blood', 'death', 'kill', 'murder',
        'hate', 'racist', 'nazi', 'terrorist', 'bomb', 'weapon'
    ]
    
    @staticmethod
    def validate_prompt(prompt: str) -> dict:
        """
        Validate and sanitize a text prompt.
        
        Args:
            prompt: The input prompt to validate
            
        Returns:
            Dictionary with validation results and sanitized prompt
        """
        if not prompt:
            return {
                'valid': False,
                'error': 'Prompt is required',
                'sanitized_prompt': ''
            }
        
        # Convert to string and strip whitespace
        prompt = str(prompt).strip()
        
        # Check if empty after stripping
        if not prompt:
            return {
                'valid': False,
                'error': 'Prompt cannot be empty',
                'sanitized_prompt': ''
            }
        
        # Check length limits (Requirements 1.3)
        if len(prompt) > 500:
            return {
                'valid': False,
                'error': 'Prompt must be 500 characters or less',
                'sanitized_prompt': prompt[:500]
            }
        
        # Check minimum length
        if len(prompt) < 3:
            return {
                'valid': False,
                'error': 'Prompt must be at least 3 characters long',
                'sanitized_prompt': prompt
            }
        
        # Sanitize HTML entities
        sanitized = html.escape(prompt)
        
        # Remove potentially harmful patterns
        for pattern in InputValidator.HARMFUL_PATTERNS:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        # Check for inappropriate content (basic filtering)
        prompt_lower = sanitized.lower()
        for keyword in InputValidator.INAPPROPRIATE_KEYWORDS:
            if keyword in prompt_lower:
                return {
                    'valid': False,
                    'error': 'Prompt contains inappropriate content',
                    'sanitized_prompt': sanitized
                }
        
        # Remove excessive whitespace and normalize
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        # Final length check after sanitization
        if len(sanitized) > 500:
            sanitized = sanitized[:500].strip()
        
        return {
            'valid': True,
            'error': None,
            'sanitized_prompt': sanitized
        }
    
    @staticmethod
    def validate_dimensions(width: int, height: int) -> dict:
        """
        Validate image dimensions.
        
        Args:
            width: Image width in pixels
            height: Image height in pixels
            
        Returns:
            Dictionary with validation results
        """
        try:
            width = int(width)
            height = int(height)
        except (ValueError, TypeError):
            return {
                'valid': False,
                'error': 'Width and height must be valid integers'
            }
        
        # Check minimum dimensions
        if width < 256 or height < 256:
            return {
                'valid': False,
                'error': 'Width and height must be at least 256 pixels'
            }
        
        # Check maximum dimensions
        if width > 2048 or height > 2048:
            return {
                'valid': False,
                'error': 'Width and height must not exceed 2048 pixels'
            }
        
        # Check aspect ratio (prevent extremely narrow images)
        aspect_ratio = max(width, height) / min(width, height)
        if aspect_ratio > 4.0:
            return {
                'valid': False,
                'error': 'Aspect ratio must not exceed 4:1'
            }
        
        return {
            'valid': True,
            'error': None,
            'width': width,
            'height': height
        }
    
    @staticmethod
    def validate_seed(seed) -> dict:
        """
        Validate random seed parameter.
        
        Args:
            seed: Seed value to validate
            
        Returns:
            Dictionary with validation results
        """
        if seed is None:
            return {
                'valid': True,
                'error': None,
                'seed': None
            }
        
        try:
            seed = int(seed)
        except (ValueError, TypeError):
            return {
                'valid': False,
                'error': 'Seed must be a valid integer'
            }
        
        # Check seed range (reasonable limits)
        if seed < 0:
            return {
                'valid': False,
                'error': 'Seed must be a non-negative integer'
            }
        
        if seed > 2**32 - 1:
            return {
                'valid': False,
                'error': 'Seed value is too large'
            }
        
        return {
            'valid': True,
            'error': None,
            'seed': seed
        }
    
    @staticmethod
    def validate_model(model: str) -> dict:
        """
        Validate model selection.
        
        Args:
            model: Model name to validate
            
        Returns:
            Dictionary with validation results
        """
        if not model:
            return {
                'valid': True,
                'error': None,
                'model': 'flux'  # Default model
            }
        
        model = str(model).strip().lower()
        
        valid_models = ['flux', 'turbo']
        
        if model not in valid_models:
            return {
                'valid': False,
                'error': f'Model must be one of: {", ".join(valid_models)}'
            }
        
        return {
            'valid': True,
            'error': None,
            'model': model
        }

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-key-change-in-production'

# Serve generated images as static files
from flask import send_from_directory

@app.route('/generated_images/<path:filename>')
def generated_images(filename):
    return send_from_directory('generated_images', filename)

@app.route('/images_to_display/<filename>')
def display_images(filename):
    return send_from_directory('images_to_display', filename)

# Initialize services
from services.file_manager import FileManager
from services.image_generator import ImageGenerationService

file_manager = FileManager()
image_generator = ImageGenerationService(file_manager)

@app.route('/')
def index():
    return send_file('index.html')

@app.route('/app')
def app_page():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/test', methods=['POST'])
def test_endpoint():
    print("Test endpoint called")
    data = request.get_json()
    print(f"Test data: {data}")
    return jsonify({'status': 'success', 'received': data})

@app.route('/generate', methods=['POST'])
def generate_image():
    print("=== GENERATE ENDPOINT CALLED ===")
    try:
        data = request.get_json()
        print(f"Raw request data: {data}")
        
        if not data:
            print("ERROR: No JSON data received")
            return jsonify({'error': 'No data received'}), 400
            
        if not data.get('prompt'):
            print("ERROR: No prompt in data")
            return jsonify({'error': 'Prompt is required'}), 400
        
        prompt = data['prompt']
        width = data.get('width', 1024)
        height = data.get('height', 1024)
        model = data.get('model', 'flux')
        seed = data.get('seed')
        
        print(f"Parsed parameters:")
        print(f"  prompt: '{prompt}'")
        print(f"  width: {width}")
        print(f"  height: {height}")
        print(f"  model: {model}")
        print(f"  seed: {seed}")
        
        print("Starting image generation...")
        result = image_generator.generate_and_save_image(
            prompt=prompt,
            width=width,
            height=height,
            seed=seed,
            model=model
        )
        
        print(f"SUCCESS: Generated {result['file_info']['filename']}")
        
        response = {
            'success': True,
            'filename': result['file_info']['filename'],
            'download_url': f"/download/{result['file_info']['filename']}",
            'generation_time': result['generation_time'],
            'file_size': result['file_info']['size']
        }
        print(f"Returning response: {response}")
        return jsonify(response)
        
    except Exception as e:
        print(f"ERROR in generate_image: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_image(filename):
    try:
        filepath = file_manager.get_file_path(filename)
        if filepath.exists():
            return send_file(str(filepath), as_attachment=True)
        return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500



if __name__ == '__main__':
    app.run(debug=True, port=5000)