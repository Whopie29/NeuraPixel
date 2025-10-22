// AI Image Generator - Main JavaScript
class ImageGenerator {
    constructor() {
        this.initializeElements();
        this.bindEvents();
        this.setupAspectRatioHandler();
    }

    initializeElements() {
        this.promptInput = document.getElementById('prompt');
        this.modelSelect = document.getElementById('model');
        this.aspectRatioSelect = document.getElementById('aspect-ratio');
        this.widthInput = document.getElementById('width');
        this.heightInput = document.getElementById('height');
        this.generateBtn = document.getElementById('generate-btn');
        this.downloadBtn = document.getElementById('download-btn');
        
        this.outputContainer = document.getElementById('output-container');
        this.outputPlaceholder = document.getElementById('output-placeholder');
        this.outputResult = document.getElementById('output-result');
        this.generatedImage = document.getElementById('generated-image');
        this.loading = document.getElementById('loading');
        
        this.filenameSpan = document.getElementById('filename');
        this.generationTimeSpan = document.getElementById('generation-time');
        this.fileSizeSpan = document.getElementById('file-size');
    }

    bindEvents() {
        this.generateBtn.addEventListener('click', () => this.generateImage());
        this.downloadBtn.addEventListener('click', () => this.downloadImage());
        this.promptInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.generateImage();
            }
        });
    }

    setupAspectRatioHandler() {
        this.aspectRatioSelect.addEventListener('change', () => {
            const ratio = this.aspectRatioSelect.value;
            const baseSize = 1024;
            
            switch(ratio) {
                case 'square':
                    this.widthInput.value = baseSize;
                    this.heightInput.value = baseSize;
                    break;
                case 'portrait':
                    this.widthInput.value = Math.round(baseSize * 0.8);
                    this.heightInput.value = baseSize;
                    break;
                case 'landscape':
                    this.widthInput.value = Math.round(baseSize * 1.78);
                    this.heightInput.value = baseSize;
                    break;
                case 'widescreen':
                    this.widthInput.value = Math.round(baseSize * 2.33);
                    this.heightInput.value = baseSize;
                    break;
            }
        });
    }

    async generateImage() {
        const prompt = this.promptInput.value.trim();
        
        if (!prompt) {
            this.showError('Please enter a prompt');
            return;
        }

        if (prompt.length > 500) {
            this.showError('Prompt must be 500 characters or less');
            return;
        }

        const requestData = {
            prompt: prompt,
            model: this.modelSelect.value,
            width: parseInt(this.widthInput.value),
            height: parseInt(this.heightInput.value)
        };

        this.setLoadingState(true);

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
            });

            const result = await response.json();

            if (response.ok && result.success) {
                this.displayResult(result);
            } else {
                this.showError(result.error || 'Generation failed');
            }
        } catch (error) {
            console.error('Error:', error);
            this.showError('Network error. Please try again.');
        } finally {
            this.setLoadingState(false);
        }
    }

    setLoadingState(loading) {
        if (loading) {
            this.generateBtn.disabled = true;
            this.generateBtn.innerHTML = '<i data-feather="loader" class="mr-2 animate-spin"></i> Generating...';
            this.loading.classList.remove('hidden');
            this.outputPlaceholder.classList.add('hidden');
            this.outputResult.classList.add('hidden');
        } else {
            this.generateBtn.disabled = false;
            this.generateBtn.innerHTML = '<i data-feather="sparkles" class="mr-2"></i> Generate Image';
            this.loading.classList.add('hidden');
        }
        feather.replace();
    }

    displayResult(result) {
        this.generatedImage.src = result.download_url;
        this.filenameSpan.textContent = result.filename;
        this.generationTimeSpan.textContent = `${result.generation_time.toFixed(2)}s`;
        this.fileSizeSpan.textContent = this.formatFileSize(result.file_size);
        
        this.downloadBtn.onclick = () => window.open(result.download_url, '_blank');
        
        this.outputPlaceholder.classList.add('hidden');
        this.outputResult.classList.remove('hidden');
        
        this.currentDownloadUrl = result.download_url;
    }

    downloadImage() {
        if (this.currentDownloadUrl) {
            window.open(this.currentDownloadUrl, '_blank');
        }
    }

    showError(message) {
        let errorDiv = document.getElementById('error-message');
        if (!errorDiv) {
            errorDiv = document.createElement('div');
            errorDiv.id = 'error-message';
            errorDiv.className = 'mt-4 p-4 bg-red-600 bg-opacity-20 border border-red-500 rounded-lg text-red-200';
            this.outputContainer.parentNode.insertBefore(errorDiv, this.outputContainer.nextSibling);
        }
        
        errorDiv.innerHTML = `
            <div class="flex items-center">
                <i data-feather="alert-circle" class="mr-2"></i>
                <span>${message}</span>
            </div>
        `;
        
        feather.replace();
        
        setTimeout(() => {
            if (errorDiv) {
                errorDiv.remove();
            }
        }, 5000);
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ImageGenerator();
});