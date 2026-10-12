import { useEffect, useState } from 'react';

export default function VideoModal() {
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const handleDocumentClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.closest('[data-open-video]')) {
        e.preventDefault();
        setIsOpen(true);
        document.body.style.overflow = 'hidden';
      }
    };

    document.addEventListener('click', handleDocumentClick, { passive: true });
    return () => {
      document.removeEventListener('click', handleDocumentClick);
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
        document.body.style.overflow = '';
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={() => {
        setIsOpen(false);
        document.body.style.overflow = '';
      }}
    >
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-5xl z-10"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={() => {
            setIsOpen(false);
            document.body.style.overflow = '';
          }}
          className="absolute -top-10 right-0 text-white hover:text-gray-300 transition-colors p-2"
          aria-label="Cerrar modal"
        >
          <svg
            className="w-8 h-8"
            fill="currentColor"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path d="M6.2253 4.81108C5.83477 4.42056 5.20161 4.42056 4.81108 4.81108C4.42056 5.20161 4.42056 5.83477 4.81108 6.2253L10.5858 12L4.81114 17.7747C4.42062 18.1652 4.42062 18.7984 4.81114 19.1889C5.20167 19.5794 5.83483 19.5794 6.22535 19.1889L12 13.4142L17.7747 19.1889C18.1652 19.5794 18.7984 19.5794 19.1889 19.1889C19.5794 18.7984 19.5794 18.1652 19.1889 17.7747L13.4142 12L19.189 6.2253C19.5795 5.83477 19.5795 5.20161 19.189 4.81108C18.7985 4.42056 18.1653 4.42056 17.7748 4.81108L12 10.5858L6.2253 4.81108Z" />
          </svg>
        </button>
        <div className="aspect-[16/9] w-full rounded-xl overflow-hidden shadow-2xl">
          <iframe
            key="youtube-hJrImU8QN2g"
            src="https://www.youtube.com/embed/hJrImU8QN2g?autoplay=1&rel=0&enablejsapi=1"
            title="¿Quiénes somos? ¿Qué hacemos? - Aristeus"
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
            className="w-full h-full"
          />
        </div>
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