import { useState, useEffect } from 'react';

export default function VideoModal() {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const openModal = () => {
      setIsOpen(true);
      document.body.style.overflow = 'hidden';
    };

    const closeModal = () => {
      setIsOpen(false);
      document.body.style.overflow = '';
    };

    // Escuchar clicks en botones para abrir modal
    const buttons = document.querySelectorAll('[data-open-video]');
    buttons.forEach(btn => {
      btn.addEventListener('click', openModal);
    });

    // Escuchar tecla Escape
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        closeModal();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleEscape);
    }

    return () => {
      buttons.forEach(btn => {
        btn.removeEventListener('click', openModal);
      });
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen]);

  const closeModal = () => {
    setIsOpen(false);
    document.body.style.overflow = '';
  };

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={closeModal}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm"></div>
      
      {/* Modal content */}
      <div 
        className="relative w-full max-w-5xl z-10"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Botón cierre */}
        <button
          onClick={closeModal}
          className="absolute -top-10 right-0 text-white hover:text-gray-300 transition-colors p-2"
          aria-label="Cerrar modal"
        >
          <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
          </svg>
        </button>
        
        {/* Contenedor iframe responsive */}
        <div className="aspect-[16/9] w-full rounded-xl overflow-hidden shadow-2xl">
          <iframe
            src="https://www.youtube.com/embed/hJrImU8QN2g?autoplay=1"
            title="¿Quiénes somos? ¿Qué hacemos? - Aristeus"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
            className="w-full h-full"
          />
        </div>
        
        {/* Enlace fallback */}
        <div className="mt-4 text-center">
          <a
            href="https://www.youtube.com/watch?v=hJrImU8QN2g"
            target="_blank"
            rel="noopener noreferrer"
            className="text-white/80 hover:text-white text-sm transition-colors underline"
          >
            Ver en YouTube
          </a>
        </div>
      </div>
    </div>
  );
}