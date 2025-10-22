import requests
import logging
from PIL import Image
import os
import hashlib
from datetime import datetime
from typing import Optional, Dict, Any
import urllib.parse
import io
import time
import gc
import threading
# Simple FileManager class for standalone operation
class FileManager:
    def __init__(self, base_directory='generated_images'):
        self.base_directory = base_directory
        os.makedirs(base_directory, exist_ok=True)
    
    def create_filename(self, prompt, extension):
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        return f"{timestamp}_{prompt_hash}.{extension}"
    
    def save_file(self, data, filename):
        filepath = os.path.join(self.base_directory, filename)
        with open(filepath, 'wb') as f:
            f.write(data)
        return {
            'filename': filename,
            'filepath': filepath,
            'relative_path': filepath,
            'size': len(data)
        }
    
    def get_file_path(self, filename):
        from pathlib import Path
        return Path(os.path.join(self.base_directory, filename))
    
    def validate_filename(self, filename):
        return filename and '.' in filename and not '..' in filename

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImageGenerationService:
    """
    Image generation service using Pollinations AI API.
    Fast, cloud-based image generation without local model requirements.
    Includes robust error handling, timeout management, and resource cleanup.
    """
    
    def __init__(self, file_manager: Optional[FileManager] = None):
        """
        Initialize the Pollinations AI image generation service.
        
        Args:
            file_manager: FileManager instance for handling file operations
        """
        self.base_url = "https://pollinations.ai/p"
        self.file_manager = file_manager or FileManager()
        self.default_model = "flux"
        
        # Configuration for robust error handling
        self.max_retries = 3
        self.base_timeout = 30  # Base timeout in seconds
        self.max_timeout = 120  # Maximum timeout in seconds
        self.retry_delay = 2    # Initial retry delay in seconds
        
        # Service health tracking
        self.service_healthy = True
        self.last_health_check = None
        self.consecutive_failures = 0
        self.max_consecutive_failures = 5
        
        # Thread lock for thread-safe operations
        self._lock = threading.Lock()
        
        logger.info("Initialized Pollinations AI image generation service with robust error handling")
    
    def _check_service_health(self) -> bool:
        """
        Check if the Pollinations AI service is healthy and responsive.
        
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            # Simple health check with a minimal request
            test_url = f"{self.base_url}/test?width=64&height=64&model=flux"
            response = requests.head(test_url, timeout=10)
            
            if response.status_code == 200:
                with self._lock:
                    self.service_healthy = True
                    self.consecutive_failures = 0
                    self.last_health_check = datetime.now()
                logger.debug("Service health check passed")
                return True
            else:
                logger.warning(f"Service health check failed with status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"Service health check failed: {e}")
            return False
    
    def _handle_service_failure(self, error: Exception) -> None:
        """
        Handle service failures and update health status.
        
        Args:
            error: The exception that occurred
        """
        with self._lock:
            self.consecutive_failures += 1
            
            if self.consecutive_failures >= self.max_consecutive_failures:
                self.service_healthy = False
                logger.error(f"Service marked as unhealthy after {self.consecutive_failures} consecutive failures")
            
            logger.error(f"Service failure #{self.consecutive_failures}: {error}")
    
    def _attempt_service_recovery(self) -> bool:
        """
        Attempt to recover service health by performing a health check.
        
        Returns:
            True if recovery successful, False otherwise
        """
        logger.info("Attempting service recovery...")
        
        # Wait a bit before attempting recovery
        time.sleep(5)
        
        # Perform health check
        if self._check_service_health():
            logger.info("Service recovery successful")
            return True
        else:
            logger.warning("Service recovery failed")
            return False
    
    def _cleanup_resources(self) -> None:
        """
        Clean up resources and perform garbage collection.
        This helps prevent memory leaks during long-running operations.
        """
        try:
            # Force garbage collection
            gc.collect()
            logger.debug("Resource cleanup completed")
        except Exception as e:
            logger.warning(f"Error during resource cleanup: {e}")
    
    def _validate_prompt(self, prompt: str) -> str:
        """
        Validate and preprocess the input prompt with enhanced error handling.
        
        Args:
            prompt: User input prompt
            
        Returns:
            Cleaned and validated prompt
            
        Raises:
            ValueError: If prompt is invalid
        """
        try:
            if not prompt or not prompt.strip():
                raise ValueError("Prompt cannot be empty")
            
            # Clean the prompt
            cleaned_prompt = prompt.strip()
            
            # Check length limit (500 characters as per requirements)
            if len(cleaned_prompt) > 500:
                raise ValueError("Prompt exceeds maximum length of 500 characters")
            
            # Check minimum length
            if len(cleaned_prompt) < 3:
                raise ValueError("Prompt must be at least 3 characters long")
            
            # Basic content filtering - remove potentially problematic content
            cleaned_prompt = cleaned_prompt.replace('\n', ' ').replace('\r', ' ')
            
            # Remove excessive whitespace
            cleaned_prompt = ' '.join(cleaned_prompt.split())
            
            # Final validation
            if not cleaned_prompt:
                raise ValueError("Prompt is empty after cleaning")
            
            logger.debug(f"Prompt validation successful: '{cleaned_prompt[:50]}...'")
            return cleaned_prompt
            
        except ValueError:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error during prompt validation: {e}")
            raise ValueError(f"Prompt validation failed: {e}")
    
    def _build_image_url(self, prompt: str, width: int = 1024, height: int = 1024, 
                        seed: Optional[int] = None, model: str = "flux") -> str:
        """
        Build the Pollinations AI image URL.
        
        Args:
            prompt: Text description of the desired image
            width: Image width in pixels
            height: Image height in pixels
            seed: Random seed for reproducible results
            model: AI model to use (default: flux)
            
        Returns:
            Complete URL for image generation
        """
        # URL encode the prompt
        encoded_prompt = urllib.parse.quote(prompt)
        
        # Build URL with parameters using the correct format
        url = f"https://pollinations.ai/p/{encoded_prompt}?width={width}&height={height}&model={model}"
        
        if seed is not None:
            url += f"&seed={seed}"
        
        return url
    
    def _download_image(self, image_url: str, timeout: int = None) -> Image.Image:
        """
        Download image from Pollinations AI.
        
        Args:
            image_url: URL to download the image from
            timeout: Custom timeout in seconds
            
        Returns:
            PIL Image object
            
        Raises:
            RuntimeError: If download fails
        """
        try:
            logger.info(f"Downloading image from Pollinations AI...")
            
            # Simple request to get the image
            response = requests.get(image_url, timeout=timeout or 30)
            response.raise_for_status()
            
            # Convert response content to PIL Image
            image = Image.open(io.BytesIO(response.content))
            
            logger.info(f"Successfully downloaded image ({len(response.content)} bytes, {image.size})")
            
            return image
            
        except Exception as e:
            logger.error(f"Failed to download image: {e}")
            raise RuntimeError(f"Image download failed: {e}")

    
    def generate_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        model: str = "flux"
    ) -> Dict[str, Any]:
        """
        Generate an image from a text prompt using Pollinations AI with comprehensive error handling.
        
        Args:
            prompt: Text description of the desired image
            width: Image width in pixels (default: 1024)
            height: Image height in pixels (default: 1024)
            seed: Random seed for reproducible results
            model: AI model to use (default: flux)
            
        Returns:
            Dictionary containing generation results and metadata
            
        Raises:
            ValueError: If input parameters are invalid
            RuntimeError: If generation fails
        """
        # Check service health before attempting generation
        if not self.service_healthy:
            logger.warning("Service is marked as unhealthy, attempting recovery...")
            if not self._attempt_service_recovery():
                raise RuntimeError("Image generation service is currently unavailable. Please try again later.")
        
        # Validate and preprocess prompt
        try:
            validated_prompt = self._validate_prompt(prompt)
        except ValueError as e:
            logger.error(f"Prompt validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during prompt validation: {e}")
            raise ValueError(f"Prompt validation failed: {e}")
        
        # Validate other parameters
        try:
            if not isinstance(width, int) or width < 256 or width > 2048:
                raise ValueError("Width must be between 256 and 2048 pixels")
            
            if not isinstance(height, int) or height < 256 or height > 2048:
                raise ValueError("Height must be between 256 and 2048 pixels")
            
            if seed is not None and (not isinstance(seed, int) or seed < 0):
                raise ValueError("Seed must be a non-negative integer")
            
            if not isinstance(model, str) or model not in ['flux', 'turbo']:
                raise ValueError("Model must be one of: flux, turbo")
                
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Parameter validation error: {e}")
            raise ValueError(f"Invalid parameters: {e}")
        
        generation_start_time = datetime.now()
        
        try:
            logger.info(f"Starting image generation for prompt: '{validated_prompt[:50]}...' "
                       f"({width}x{height}, model: {model}, seed: {seed})")
            
            # Build image URL
            try:
                image_url = self._build_image_url(
                    prompt=validated_prompt,
                    width=width,
                    height=height,
                    seed=seed,
                    model=model
                )
                logger.debug(f"Generated image URL: {image_url}")
                
            except Exception as e:
                logger.error(f"Failed to build image URL: {e}")
                raise RuntimeError(f"Failed to prepare generation request: {e}")
            
            # Download the generated image with timeout handling
            try:
                # Calculate timeout based on image size (larger images take longer)
                estimated_timeout = max(30, (width * height) // 10000)  # Rough estimate
                timeout = min(estimated_timeout, self.max_timeout)
                
                logger.debug(f"Using timeout of {timeout} seconds for generation")
                image = self._download_image(image_url, timeout=timeout)
                
            except RuntimeError as e:
                # Handle specific download errors
                if "timed out" in str(e).lower():
                    raise RuntimeError("Image generation timed out. The request may be too complex or the service is busy. Please try again with a simpler prompt.")
                elif "too large" in str(e).lower():
                    raise RuntimeError("Generated image is too large. Please try with smaller dimensions.")
                elif "invalid" in str(e).lower():
                    raise RuntimeError("The generated image is invalid. Please try a different prompt.")
                else:
                    raise RuntimeError(f"Image generation failed: {e}")
            
            generation_time = (datetime.now() - generation_start_time).total_seconds()
            
            # Validate the generated image
            try:
                if not image or image.size[0] == 0 or image.size[1] == 0:
                    raise RuntimeError("Generated image is empty or invalid")
                
                # Check if image dimensions are reasonable
                if image.size[0] > 4096 or image.size[1] > 4096:
                    logger.warning(f"Generated image is very large: {image.size}")
                
                logger.info(f"Image generated successfully in {generation_time:.2f} seconds "
                           f"(size: {image.size}, mode: {image.mode})")
                
            except Exception as e:
                logger.error(f"Generated image validation failed: {e}")
                raise RuntimeError(f"Generated image is invalid: {e}")
            
            # Clean up resources after successful generation
            self._cleanup_resources()
            
            return {
                "success": True,
                "image": image,
                "prompt": validated_prompt,
                "generation_time": generation_time,
                "image_url": image_url,
                "parameters": {
                    "width": width,
                    "height": height,
                    "seed": seed,
                    "model": model
                },
                "metadata": {
                    "service_healthy": self.service_healthy,
                    "consecutive_failures": self.consecutive_failures,
                    "generation_timestamp": generation_start_time.isoformat()
                }
            }
            
        except ValueError:
            # Re-raise validation errors without modification
            raise
        except RuntimeError:
            # Re-raise runtime errors without modification
            raise
        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Unexpected error during image generation: {e}")
            self._handle_service_failure(e)
            self._cleanup_resources()
            raise RuntimeError(f"Image generation failed due to unexpected error: {e}")
    
    def _create_filename(self, prompt: str) -> str:
        """
        Create a unique filename based on timestamp and prompt hash using file manager.
        
        Args:
            prompt: The text prompt used for generation
            
        Returns:
            Unique filename string
        """
        return self.file_manager.create_filename(prompt, "png")
    
    def _optimize_image(self, image: Image.Image) -> Image.Image:
        """
        Optimize the image for web display and storage.
        
        Args:
            image: PIL Image object
            
        Returns:
            Optimized PIL Image object
        """
        # Convert to RGB if necessary (removes alpha channel)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        return image
    
    def save_image(self, image: Image.Image, prompt: str) -> Dict[str, str]:
        """
        Save the generated image with proper naming and organization using file manager.
        Includes comprehensive error handling and resource management.
        
        Args:
            image: PIL Image object to save
            prompt: Original prompt used for generation
            
        Returns:
            Dictionary with file information
            
        Raises:
            RuntimeError: If saving fails
        """
        if not image:
            raise RuntimeError("Cannot save empty image")
        
        try:
            # Validate image before processing
            try:
                # Check basic image properties without calling verify() which closes the image
                if not hasattr(image, 'size') or not image.size:
                    raise RuntimeError("Image has no size attribute")
                
                if image.size[0] == 0 or image.size[1] == 0:
                    raise RuntimeError("Image has zero dimensions")
                
                # Create a copy to avoid issues with the original image
                image = image.copy()
                logger.debug(f"Image validated and copied: {image.size}, mode: {image.mode}")
                    
            except Exception as e:
                logger.error(f"Image validation failed before saving: {e}")
                raise RuntimeError(f"Invalid image data: {e}")
            
            # Create unique filename with error handling
            try:
                filename = self._create_filename(prompt)
                logger.debug(f"Generated filename: {filename}")
                
            except Exception as e:
                logger.error(f"Failed to create filename: {e}")
                raise RuntimeError(f"Filename generation failed: {e}")
            
            # Optimize image with error handling
            try:
                optimized_image = self._optimize_image(image)
                logger.debug(f"Image optimized: {optimized_image.size}, mode: {optimized_image.mode}")
                
            except Exception as e:
                logger.error(f"Image optimization failed: {e}")
                # Try to save original image if optimization fails
                optimized_image = image
                logger.warning("Using original image due to optimization failure")
            
            # Convert image to bytes with error handling
            try:
                img_bytes = io.BytesIO()
                
                # Save with different quality settings based on image size
                if optimized_image.size[0] * optimized_image.size[1] > 1024 * 1024:
                    # Large image - use compression
                    optimized_image.save(img_bytes, "PNG", optimize=True, compress_level=6)
                else:
                    # Smaller image - prioritize quality
                    optimized_image.save(img_bytes, "PNG", optimize=True, compress_level=3)
                
                img_bytes.seek(0)
                image_data = img_bytes.getvalue()
                
                # Validate the saved data
                if len(image_data) == 0:
                    raise RuntimeError("Generated image data is empty")
                
                # Check file size (reasonable limits)
                if len(image_data) > 50 * 1024 * 1024:  # 50MB limit
                    raise RuntimeError("Generated image file is too large")
                
                logger.debug(f"Image converted to bytes: {len(image_data)} bytes")
                
            except Exception as e:
                logger.error(f"Image to bytes conversion failed: {e}")
                raise RuntimeError(f"Image processing failed: {e}")
            
            # Save using file manager with error handling
            try:
                file_info = self.file_manager.save_file(image_data, filename)
                
                # Validate saved file info
                if not file_info or not file_info.get('filename'):
                    raise RuntimeError("File manager returned invalid file info")
                
                logger.info(f"Image saved successfully: {file_info['filepath']} ({file_info['size']} bytes)")
                
                return {
                    "filename": file_info["filename"],
                    "filepath": file_info["filepath"],
                    "relative_path": file_info["relative_path"],
                    "size": file_info["size"]
                }
                
            except Exception as e:
                logger.error(f"File manager save failed: {e}")
                raise RuntimeError(f"File saving failed: {e}")
            
        except RuntimeError:
            # Re-raise runtime errors without modification
            raise
        except Exception as e:
            logger.error(f"Unexpected error during image saving: {e}")
            raise RuntimeError(f"Image saving failed due to unexpected error: {e}")
        finally:
            # Clean up resources
            try:
                if 'img_bytes' in locals():
                    img_bytes.close()
                self._cleanup_resources()
            except Exception as e:
                logger.warning(f"Error during save cleanup: {e}")
    
    def generate_and_save_image(
        self,
        prompt: str,
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        model: str = "flux"
    ) -> Dict[str, Any]:
        """
        Complete workflow: generate image using Pollinations AI and save it to storage.
        Includes comprehensive error handling and resource management.
        
        Args:
            prompt: Text description of the desired image
            width: Image width in pixels
            height: Image height in pixels
            seed: Random seed for reproducible results
            model: AI model to use
            
        Returns:
            Dictionary containing generation results and file information
            
        Raises:
            ValueError: If input parameters are invalid
            RuntimeError: If generation or saving fails
        """
        workflow_start_time = datetime.now()
        
        try:
            logger.info(f"Starting complete image generation workflow for prompt: '{prompt[:50]}...'")
            
            # Generate the image with comprehensive error handling
            try:
                generation_result = self.generate_image(
                    prompt=prompt,
                    width=width,
                    height=height,
                    seed=seed,
                    model=model
                )
                
                if not generation_result.get("success"):
                    logger.error("Image generation returned unsuccessful result")
                    return {
                        "success": False,
                        "error": "Image generation failed",
                        "details": generation_result
                    }
                
            except ValueError as e:
                logger.error(f"Validation error in generation workflow: {e}")
                raise  # Re-raise validation errors
            except RuntimeError as e:
                logger.error(f"Runtime error in generation workflow: {e}")
                raise  # Re-raise runtime errors
            except Exception as e:
                logger.error(f"Unexpected error during image generation: {e}")
                raise RuntimeError(f"Image generation failed: {e}")
            
            # Save the image with error handling
            try:
                file_info = self.save_image(generation_result["image"], prompt)
                
            except RuntimeError as e:
                logger.error(f"Image saving failed: {e}")
                # Clean up the generated image from memory
                if "image" in generation_result:
                    try:
                        generation_result["image"].close()
                    except:
                        pass
                raise RuntimeError(f"Failed to save generated image: {e}")
            except Exception as e:
                logger.error(f"Unexpected error during image saving: {e}")
                # Clean up the generated image from memory
                if "image" in generation_result:
                    try:
                        generation_result["image"].close()
                    except:
                        pass
                raise RuntimeError(f"Image saving failed: {e}")
            
            # Calculate total workflow time
            total_time = (datetime.now() - workflow_start_time).total_seconds()
            
            # Combine results
            result = {
                **generation_result,
                "file_info": file_info,
                "workflow_time": total_time
            }
            
            # Remove the PIL Image object from the result (not JSON serializable)
            # and clean up memory
            if "image" in result:
                try:
                    result["image"].close()
                except:
                    pass
                del result["image"]
            
            logger.info(f"Complete workflow finished successfully in {total_time:.2f} seconds")
            
            return result
            
        except ValueError:
            # Re-raise validation errors
            raise
        except RuntimeError:
            # Re-raise runtime errors
            raise
        except Exception as e:
            logger.error(f"Unexpected error in complete workflow: {e}")
            self._handle_service_failure(e)
            raise RuntimeError(f"Complete image generation workflow failed: {e}")
        finally:
            # Final cleanup
            self._cleanup_resources()