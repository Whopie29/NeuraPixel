/**
 * AI Image Generator Frontend JavaScript
 * Handles form submission, API communication, loading states, and image display
 */

class ImageGenerator {
    constructor() {
        this.initializeElements();
        this.bindEvents();
        this.isGenerating = false;
        this.currentImageData = null;
    }

    /**
     * Initialize DOM elements
     */
    initializeElements() {
        // Form elements
        this.promptInput = document.getElementById('prompt');
        this.modelSelect = document.getElementById('model');
        this.sizeSelect = document.getElementById('size');
        this.widthInput = document.getElementById('width');
        this.heightInput = document.getElementById('height');
        this.seedInput = document.getElementById('seed');
        this.generateButton = document.getElementById('generateBtn');
        this.customSizeContainer = document.getElementById('customSizeContainer');
        
        // Image display elements
        this.outputContainer = document.getElementById('outputContainer');
        this.placeholder = document.getElementById('placeholder');
        this.generatedImage = document.getElementById('generatedImage');
        this.imageInfo = document.getElementById('imageInfo');
        this.filename = document.getElementById('filename');
        this.generationTime = document.getElementById('generationTime');
        this.fileSize = document.getElementById('fileSize');
        this.downloadButton = document.getElementById('downloadBtn');
    }

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Size selector change
        this.sizeSelect.addEventListener('change', (e) => this.handleSizeChange(e));
        
        // Enter key in prompt input
        this.promptInput.addEventListener('keydown', (e) => this.handleKeyDown(e));
        
        // Generate button click
        this.generateButton.addEventListener('click', (e) => this.handleGenerateClick(e));
        
        // Download button click
        this.downloadButton.addEventListener('click', (e) => this.handleDownloadClick(e));
        
        // Image load events
        this.generatedImage.addEventListener('load', () => this.handleImageLoad());
        this.generatedImage.addEventListener('error', () => this.handleImageError());
    }

    /**
     * Handle size selector change
     */
    handleSizeChange(event) {
        const value = event.target.value;
        if (value === 'custom') {
            this.customSizeContainer.classList.remove('hidden');
        } else {
            this.customSizeContainer.classList.add('hidden');
        }
    }

    /**
     * Handle Enter key press in prompt input
     */
    handleKeyDown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            if (!this.isGenerating && this.validatePrompt()) {
                this.generateImage();
            }
        }
    }

    /**
     * Handle generate button click
     */
    async handleGenerateClick(event) {
        event.preventDefault();
        
        if (this.isGenerating) {
            return;
        }
        
        if (!this.validatePrompt()) {
            return;
        }
        
        await this.generateImage();
    }

    /**
     * Validate prompt input
     */
    validatePrompt() {
        const prompt = this.promptInput.value.trim();
        
        if (prompt.length === 0) {
            this.showError('Please enter a prompt to generate an image.');
            return false;
        }
        
        if (prompt.length > 500) {
            this.showError('Prompt must be 500 characters or less.');
            return false;
        }
        
        return true;
    }

    /**
     * Get image dimensions from form
     */
    getDimensions() {
        const sizeValue = this.sizeSelect.value;
        
        if (sizeValue === 'custom') {
            const width = parseInt(this.widthInput.value) || 1024;
            const height = parseInt(this.heightInput.value) || 1024;
            return { width, height };
        } else {
            const [width, height] = sizeValue.split('x').map(Number);
            return { width, height };
        }
    }

    /**
     * Generate image via API call
     */
    async generateImage() {
        const prompt = this.promptInput.value.trim();
        const { width, height } = this.getDimensions();
        const model = this.modelSelect.value;
        const seed = this.seedInput.value ? parseInt(this.seedInput.value) : null;
        const startTime = Date.now();
        
        try {
            // Set loading state
            this.setLoadingState(true);
            this.hideImageDisplay();
            
            // Prepare request data
            const requestData = {
                prompt: prompt,
                width: width,
                height: height,
                model: model
            };
            
            if (seed !== null) {
                requestData.seed = seed;
            }
            
            // Make API request
            const response = await this.makeApiRequest('/generate', requestData);
            
            // Handle response
            if (response.success) {
                const generationTime = (Date.now() - startTime) / 1000;
                this.displayGeneratedImage(response, generationTime);
            } else {
                throw new Error(response.error || 'Image generation failed');
            }
            
        } catch (error) {
            console.error('Image generation error:', error);
            this.handleGenerationError(error);
        } finally {
            this.setLoadingState(false);
        }
    }

    /**
     * Make API request with proper error handling
     */
    async makeApiRequest(endpoint, data) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minute timeout
        
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `Server error: ${response.status}`);
            }
            
            const result = await response.json();
            return result;
            
        } catch (error) {
            clearTimeout(timeoutId);
            
            if (error.name === 'AbortError') {
                throw new Error('Request timed out. Please try again.');
            }
            
            if (error instanceof TypeError && error.message.includes('fetch')) {
                throw new Error('Network error. Please check your connection and try again.');
            }
            
            throw error;
        }
    }

    /**
     * Set button loading state
     */
    setLoadingState(isLoading) {
        this.isGenerating = isLoading;
        
        if (isLoading) {
            // Show loading state
            this.generateButton.disabled = true;
            this.generateButton.innerHTML = '<i data-feather="loader" class="mr-2 animate-spin"></i> Generating...';
            this.generateButton.classList.add('opacity-75', 'cursor-not-allowed');
            
            // Disable form inputs during generation
            this.promptInput.disabled = true;
            this.modelSelect.disabled = true;
            this.sizeSelect.disabled = true;
            this.widthInput.disabled = true;
            this.heightInput.disabled = true;
            this.seedInput.disabled = true;
        } else {
            // Show default state
            this.generateButton.disabled = false;
            this.generateButton.innerHTML = '<i data-feather="zap" class="mr-2"></i> Generate Image';
            this.generateButton.classList.remove('opacity-75', 'cursor-not-allowed');
            
            // Re-enable form inputs
            this.promptInput.disabled = false;
            this.modelSelect.disabled = false;
            this.sizeSelect.disabled = false;
            this.widthInput.disabled = false;
            this.heightInput.disabled = false;
            this.seedInput.disabled = false;
            
            // Replace feather icons
            feather.replace();
        }
    }

    /**
     * Handle generation errors with specific error types
     */
    handleGenerationError(error) {
        let errorMessage = 'Failed to generate image. Please try again.';
        
        if (error.message) {
            if (error.message.includes('timeout') || error.message.includes('timed out')) {
                errorMessage = 'Request timed out. The AI model may be busy. Please try again in a moment.';
            } else if (error.message.includes('network') || error.message.includes('Network')) {
                errorMessage = 'Network error. Please check your internet connection and try again.';
            } else if (error.message.includes('server error') || error.message.includes('Server error')) {
                errorMessage = 'Server error. Please try again later.';
            } else if (error.message.includes('not yet implemented')) {
                errorMessage = 'Image generation service is not yet available. Please check back later.';
            } else {
                errorMessage = error.message;
            }
        }
        
        this.showError(errorMessage);
    }

    /**
     * Show error message
     */
    showError(message) {
        // Create error notification
        const errorDiv = document.createElement('div');
        errorDiv.className = 'fixed top-4 right-4 bg-red-500 text-white px-6 py-3 rounded-lg shadow-lg z-50 max-w-md';
        errorDiv.innerHTML = `
            <div class="flex items-center">
                <i data-feather="alert-circle" class="mr-2"></i>
                <span>${message}</span>
                <button class="ml-4 text-white hover:text-gray-200" onclick="this.parentElement.parentElement.remove()">
                    <i data-feather="x"></i>
                </button>
            </div>
        `;
        
        document.body.appendChild(errorDiv);
        feather.replace();
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentElement) {
                errorDiv.remove();
            }
        }, 5000);
    }

    /**
     * Display generated image
     */
    displayGeneratedImage(response, generationTime) {
        // Hide placeholder
        this.placeholder.classList.add('hidden');
        
        // Set image source
        this.generatedImage.src = response.download_url;
        this.generatedImage.alt = `Generated image: ${response.sanitized_prompt}`;
        this.generatedImage.classList.remove('hidden');
        
        // Store image data for download functionality
        this.currentImageData = {
            url: response.download_url,
            filename: response.filename,
            prompt: response.sanitized_prompt,
            generationTime: generationTime
        };
        
        // Update image info
        this.filename.textContent = response.filename;
        this.generationTime.textContent = `${generationTime.toFixed(1)}s`;
        this.fileSize.textContent = this.formatFileSize(response.file_size);
        
        // Show image info and download button
        this.imageInfo.classList.remove('hidden');
        this.downloadButton.classList.remove('hidden');
        
        // Set download button
        this.downloadButton.onclick = () => {
            const link = document.createElement('a');
            link.href = response.download_url;
            link.download = response.filename;
            link.click();
        };
    }

    /**
     * Format file size for display
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * Hide image display
     */
    hideImageDisplay() {
        this.placeholder.classList.remove('hidden');
        this.generatedImage.classList.add('hidden');
        this.imageInfo.classList.add('hidden');
        this.downloadButton.classList.add('hidden');
    }

    /**
     * Handle successful image load
     */
    handleImageLoad() {
        console.log('Image loaded successfully');
    }

    /**
     * Handle image load error
     */
    handleImageError() {
        console.error('Failed to load generated image');
        this.showError('Failed to load the generated image. Please try again.');
        this.hideImageDisplay();
    }

    /**
     * Handle download button click
     */
    handleDownloadClick(event) {
        try {
            // Check if we have current image data
            if (!this.currentImageData) {
                event.preventDefault();
                this.showError('No image available for download. Please generate an image first.');
                return;
            }
            
            console.log('Download initiated for:', this.currentImageData.filename);
            
        } catch (error) {
            console.error('Download error:', error);
            event.preventDefault();
            this.showError('Failed to download image. Please try again.');
        }
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    new ImageGenerator();
});