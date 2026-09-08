document.addEventListener('DOMContentLoaded', () => {
    const toggleBtn = document.getElementById('theme-toggle');
    const storedTheme = localStorage.getItem('caliga-theme') || 
        (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

    document.documentElement.setAttribute('data-theme', storedTheme);

    if (toggleBtn) {
        toggleBtn.innerText = storedTheme === 'dark' ? 'Light' : 'Dark';
        toggleBtn.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('caliga-theme', newTheme);
            toggleBtn.innerText = newTheme === 'dark' ? 'Light' : 'Dark';
        });
    }
});