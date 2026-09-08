import React, { useState, useEffect } from 'react';
import {
  MapContainer,
  TileLayer,
  Polygon,
  Polyline,
  Marker,
  Tooltip,
  useMap,
  useMapEvents,
  ImageOverlay
} from 'react-leaflet';
import type { LatLngExpression, LeafletMouseEvent } from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default Leaflet icon issues in React
import L from 'leaflet';
const customIcon = new L.Icon({
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41]
});

// Tipos de datos preparados para backend y BD SQL
export interface ParcelData {
  id: string;
  code: string; // ej: Parcela 1, Sub-Lote A
  pastureId: string;
  coordinates: [number, number][]; // Polígono irregular dibujado [lat, lng]
  biomassMS: number; // kg MS / ha
  dryMatterPercent?: number; // %
  grassHeightCm?: number;
  sampleDate?: string;
  samplePhotoUrl?: string;
  notes?: string;
}

export interface PastureData {
  id: string;
  name: string;
  color: string;
  areaHa: number;
  grassType: string;
  coordinates: [number, number][]; // Polígono [lat, lng]
  defaultBiomassMS: number; // kg MS/ha estimado por defecto
  status: 'available' | 'resting' | 'depleted';
  parcels: ParcelData[];
  createdAt: string;
}

export interface FarmData {
  id: string;
  name: string;
  ownerName: string;
  locationName: string;
  center: [number, number];
  perimeterCoordinates: [number, number][];
  totalAreaHa: number;
  pastures: PastureData[];
  updatedAt: string;
}

// Coordenadas de la Estancia Sujalito (Captura 116 - Zona 2WHV+87 Santa Cruz, Bolivia)
const DEFAULT_CENTER: [number, number] = [-17.4125, -63.2842];
const DEFAULT_ZOOM = 15;

// Datos iniciales de demostración con parcelas personalizadas dibujadas a mano
const INITIAL_FARM: FarmData = {
  id: 'farm-sujalito-01',
  name: 'Estancia Sujalito',
  ownerName: 'Ganadería Modelo',
  locationName: 'Sujalito (2WHV+87) - Santa Cruz',
  center: DEFAULT_CENTER,
  perimeterCoordinates: [
    [-17.3980, -63.2980],
    [-17.3960, -63.2680],
    [-17.4080, -63.2620],
    [-17.4240, -63.2640],
    [-17.4290, -63.2920],
    [-17.4190, -63.3010],
  ],
  totalAreaHa: 480,
  updatedAt: new Date().toISOString(),
  pastures: [
    {
      id: 'pasture-01',
      name: 'Potrero Norte (Braquiaria)',
      color: '#6BA539',
      areaHa: 95,
      grassType: 'Brachiaria brizantha',
      defaultBiomassMS: 2350,
      status: 'available',
      createdAt: new Date().toISOString(),
      coordinates: [
        [-17.4000, -63.2920],
        [-17.3990, -63.2750],
        [-17.4080, -63.2730],
        [-17.4090, -63.2900],
      ],
      parcels: [
        {
          id: 'parcel-demo-1',
          code: 'Sector Norte A',
          pastureId: 'pasture-01',
          biomassMS: 2450,
          dryMatterPercent: 26,
          grassHeightCm: 45,
          sampleDate: new Date().toISOString().split('T')[0],
          notes: 'Sector alto con excelente rebrote',
          coordinates: [
            [-17.4005, -63.2915],
            [-17.3995, -63.2830],
            [-17.4040, -63.2825],
            [-17.4045, -63.2910],
          ]
        },
        {
          id: 'parcel-demo-2',
          code: 'Sector Norte B',
          pastureId: 'pasture-01',
          biomassMS: 1850,
          dryMatterPercent: 24,
          grassHeightCm: 32,
          sampleDate: new Date().toISOString().split('T')[0],
          notes: 'Sector con humedad media',
          coordinates: [
            [-17.3995, -63.2825],
            [-17.3992, -63.2755],
            [-17.4042, -63.2740],
            [-17.4040, -63.2820],
          ]
        }
      ]
    },
    {
      id: 'pasture-02',
      name: 'Potrero Centro (Mombaza)',
      color: '#355E3B',
      areaHa: 110,
      grassType: 'Panicum maximum cv. Mombasa',
      defaultBiomassMS: 1650,
      status: 'resting',
      createdAt: new Date().toISOString(),
      coordinates: [
        [-17.4095, -63.2910],
        [-17.4085, -63.2725],
        [-17.4180, -63.2710],
        [-17.4190, -63.2890],
      ],
      parcels: []
    },
    {
      id: 'pasture-03',
      name: 'Potrero Sur (Bajo)',
      color: '#0B2341',
      areaHa: 80,
      grassType: 'Brachiaria humidicola',
      defaultBiomassMS: 850,
      status: 'depleted',
      createdAt: new Date().toISOString(),
      coordinates: [
        [-17.4195, -63.2885],
        [-17.4185, -63.2705],
        [-17.4270, -63.2690],
        [-17.4280, -63.2870],
      ],
      parcels: []
    }
  ]
};

// Utilidad para calcular gradiente de color de Materia Seca (Heatmap HU-4)
export function getBiomassColor(biomass: number): { fill: string; stroke: string; label: string; bgClass: string; textClass: string } {
  if (biomass >= 2200) {
    return {
      fill: '#4E9E2A',
      stroke: '#355E3B',
      label: 'Excelente (> 2200 kg MS/ha)',
      bgClass: 'bg-emerald-600',
      textClass: 'text-emerald-400'
    };
  } else if (biomass >= 1600) {
    return {
      fill: '#6BA539',
      stroke: '#4E9E2A',
      label: 'Óptima (1600 - 2200 kg MS/ha)',
      bgClass: 'bg-lime-600',
      textClass: 'text-lime-400'
    };
  } else if (biomass >= 1000) {
    return {
      fill: '#E5A93C',
      stroke: '#C48825',
      label: 'Media / Aceptable (1000 - 1600 kg MS/ha)',
      bgClass: 'bg-amber-500',
      textClass: 'text-amber-400'
    };
  } else {
    return {
      fill: '#E05345',
      stroke: '#B83224',
      label: 'Baja / Crítica (< 1000 kg MS/ha)',
      bgClass: 'bg-red-500',
      textClass: 'text-red-400'
    };
  }
}

// Componente para capturar clicks de dibujo de vértices con cursor
interface MapClickHandlerProps {
  drawMode: 'none' | 'perimeter' | 'pasture' | 'parcel';
  onAddPoint: (latlng: [number, number]) => void;
}

function MapClickHandler({ drawMode, onAddPoint }: MapClickHandlerProps) {
  useMapEvents({
    click(e: LeafletMouseEvent) {
      if (drawMode !== 'none') {
        onAddPoint([e.latlng.lat, e.latlng.lng]);
      }
    }
  });
  return null;
}

// Recenter Map Helper
function ChangeView({ center, zoom }: { center: [number, number]; zoom: number }) {
  const map = useMap();
  useEffect(() => {
    map.setView(center, zoom);
  }, [center, zoom, map]);
  return null;
}

export default function FarmManager() {
  const [mounted, setMounted] = useState(false);
  const [farm, setFarm] = useState<FarmData>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('aristeus_farm_data');
      if (saved) {
        try {
          return JSON.parse(saved);
        } catch (e) {
          console.error('Error parsing saved farm data:', e);
        }
      }
    }
    return INITIAL_FARM;
  });

  // Capas y modos de visualización
  const [mapLayer, setMapLayer] = useState<'satellite' | 'dark'>('satellite');
  const [viewMode, setViewMode] = useState<'heatmap' | 'pastures' | 'both'>('heatmap');
  
  // Modos de dibujo interactivo con cursor (HU-1 & HU-3)
  const [drawMode, setDrawMode] = useState<'none' | 'perimeter' | 'pasture' | 'parcel'>('none');
  const [draftPoints, setDraftPoints] = useState<[number, number][]>([]);
  
  // Campos para nuevos elementos dibujados
  const [newPastureName, setNewPastureName] = useState('');
  const [newPastureGrass, setNewPastureGrass] = useState('Brachiaria brizantha');
  const [newPastureMS, setNewPastureMS] = useState(2000);
  const [newParcelCode, setNewParcelCode] = useState('');
  const [newParcelMS, setNewParcelMS] = useState(2100);

  // Elementos seleccionados
  const [selectedPastureId, setSelectedPastureId] = useState<string | null>('pasture-01');
  const [selectedParcel, setSelectedParcel] = useState<ParcelData | null>(null);
  
  // Modal de muestreo / edición de parcela
  const [isSamplingModalOpen, setIsSamplingModalOpen] = useState(false);
  const [manualMSValue, setManualMSValue] = useState<number>(2000);
  const [manualGrassHeight, setManualGrassHeight] = useState<number>(30);
  const [manualDryMatterPct, setManualDryMatterPct] = useState<number>(25);
  const [manualParcelCode, setManualParcelCode] = useState<string>('');
  const [samplePhotoPreview, setSamplePhotoPreview] = useState<string>('');
  const [sampleNotes, setSampleNotes] = useState<string>('');
  const [isSimulatingML, setIsSimulatingML] = useState(false);

  // Modal BD & Notificación
  const [isDbModalOpen, setIsDbModalOpen] = useState(false);
  const [notification, setNotification] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Guardar en localStorage de forma persistente
  useEffect(() => {
    if (mounted && typeof window !== 'undefined') {
      localStorage.setItem('aristeus_farm_data', JSON.stringify(farm));
    }
  }, [farm, mounted]);

  const showNotification = (msg: string) => {
    setNotification(msg);
    setTimeout(() => setNotification(null), 4000);
  };

  const selectedPasture = farm.pastures.find(p => p.id === selectedPastureId) || farm.pastures[0];

  // Agregar vértice con el cursor
  const handleAddDraftPoint = (latlng: [number, number]) => {
    setDraftPoints(prev => [...prev, latlng]);
  };

  // Deshacer el último vértice colocado
  const handleUndoLastPoint = () => {
    setDraftPoints(prev => prev.slice(0, -1));
  };

  // Guardar Perímetro de la Finca (HU-1)
  const handleSavePerimeter = () => {
    if (draftPoints.length < 3) {
      alert('Se requieren al menos 3 vértices para definir el perímetro.');
      return;
    }
    setFarm(prev => ({
      ...prev,
      perimeterCoordinates: draftPoints,
      updatedAt: new Date().toISOString()
    }));
    setDraftPoints([]);
    setDrawMode('none');
    showNotification('✅ Perímetro de la finca guardado exitosamente.');
  };

  // Guardar Nuevo Potrero Dibujado (HU-1)
  const handleSaveNewPasture = () => {
    if (draftPoints.length < 3) {
      alert('Se requieren al menos 3 vértices para delimitar el potrero.');
      return;
    }
    if (!newPastureName.trim()) {
      alert('Por favor ingrese un nombre para el potrero.');
      return;
    }

    const newId = `pasture-${Date.now()}`;
    const newPasture: PastureData = {
      id: newId,
      name: newPastureName.trim(),
      color: '#6BA539',
      areaHa: Math.round(draftPoints.length * 12),
      grassType: newPastureGrass,
      defaultBiomassMS: Number(newPastureMS) || 1800,
      status: 'available',
      coordinates: draftPoints,
      parcels: [],
      createdAt: new Date().toISOString()
    };

    setFarm(prev => ({
      ...prev,
      pastures: [...prev.pastures, newPasture],
      updatedAt: new Date().toISOString()
    }));

    setDraftPoints([]);
    setDrawMode('none');
    setNewPastureName('');
    setSelectedPastureId(newId);
    showNotification(`✅ Potrero "${newPasture.name}" guardado exitosamente.`);
  };

  // Guardar Parcela Dibujada con Vértices Personalizados (HU-3)
  const handleSaveDrawnParcel = () => {
    if (!selectedPasture) {
      alert('Debe seleccionar un potrero primero.');
      return;
    }
    if (draftPoints.length < 3) {
      alert('Se requieren al menos 3 vértices para delimitar la parcela.');
      return;
    }

    const parcelCode = newParcelCode.trim() || `Parcela ${selectedPasture.parcels.length + 1}`;
    const newParcel: ParcelData = {
      id: `parcel-${Date.now()}`,
      code: parcelCode,
      pastureId: selectedPasture.id,
      coordinates: draftPoints,
      biomassMS: Number(newParcelMS) || selectedPasture.defaultBiomassMS || 2000,
      dryMatterPercent: 25,
      grassHeightCm: 35,
      sampleDate: new Date().toISOString().split('T')[0],
      samplePhotoUrl: '',
      notes: 'Parcela dibujada por el ganadero'
    };

    setFarm(prev => ({
      ...prev,
      pastures: prev.pastures.map(p => 
        p.id === selectedPasture.id
          ? { ...p, parcels: [...p.parcels, newParcel] }
          : p
      ),
      updatedAt: new Date().toISOString()
    }));

    setDraftPoints([]);
    setDrawMode('none');
    setNewParcelCode('');
    showNotification(`🌱 Parcela "${parcelCode}" guardada en ${selectedPasture.name}.`);
  };

  // Eliminar un potrero
  const handleDeletePasture = (pastureId: string) => {
    const target = farm.pastures.find(p => p.id === pastureId);
    if (!target) return;
    if (confirm(`¿Estás seguro de que deseas eliminar el potrero "${target.name}" y todas sus parcelas?`)) {
      setFarm(prev => ({
        ...prev,
        pastures: prev.pastures.filter(p => p.id !== pastureId),
        updatedAt: new Date().toISOString()
      }));
      if (selectedPastureId === pastureId) {
        const remaining = farm.pastures.filter(p => p.id !== pastureId);
        setSelectedPastureId(remaining.length > 0 ? remaining[0].id : null);
      }
      showNotification(`🗑️ Potrero "${target.name}" eliminado.`);
    }
  };

  // Eliminar una parcela individual
  const handleDeleteParcel = (parcelId: string, pastureId: string) => {
    if (confirm('¿Deseas eliminar esta parcela?')) {
      setFarm(prev => ({
        ...prev,
        pastures: prev.pastures.map(p => 
          p.id === pastureId
            ? { ...p, parcels: p.parcels.filter(parcel => parcel.id !== parcelId) }
            : p
        ),
        updatedAt: new Date().toISOString()
      }));
      setIsSamplingModalOpen(false);
      setSelectedParcel(null);
      showNotification('🗑️ Parcela eliminada.');
    }
  };

  // Borrar todas las parcelas de un potrero si el usuario quiere redibujarlas
  const handleClearAllParcels = (pastureId: string) => {
    const target = farm.pastures.find(p => p.id === pastureId);
    if (!target) return;
    if (confirm(`¿Deseas eliminar todas las parcelas del potrero "${target.name}" para redibujarlas?`)) {
      setFarm(prev => ({
        ...prev,
        pastures: prev.pastures.map(p => 
          p.id === pastureId ? { ...p, parcels: [] } : p
        ),
        updatedAt: new Date().toISOString()
      }));
      showNotification(`🗑️ Parcelas de "${target.name}" eliminadas.`);
    }
  };

  // Abrir modal de edición/muestreo
  const handleOpenSampling = (parcel: ParcelData) => {
    setSelectedParcel(parcel);
    setManualParcelCode(parcel.code);
    setManualMSValue(parcel.biomassMS);
    setManualGrassHeight(parcel.grassHeightCm || 30);
    setManualDryMatterPct(parcel.dryMatterPercent || 25);
    setSamplePhotoPreview(parcel.samplePhotoUrl || '');
    setSampleNotes(parcel.notes || '');
    setIsSamplingModalOpen(true);
  };

  // Subida de fotografía
  const handlePhotoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onloadend = () => {
      setSamplePhotoPreview(reader.result as string);
    };
    reader.readAsDataURL(file);
  };

  // Simulación de Machine Learning
  const handleSimulateML = () => {
    setIsSimulatingML(true);
    setTimeout(() => {
      const mlEstimate = Math.round(1400 + Math.random() * 1200);
      const mlHeight = Math.round(20 + Math.random() * 40);
      const mlDryPct = Math.round(20 + Math.random() * 10);
      setManualMSValue(mlEstimate);
      setManualGrassHeight(mlHeight);
      setManualDryMatterPct(mlDryPct);
      setIsSimulatingML(false);
      showNotification(`✨ Modelo ML estimó: ${mlEstimate.toLocaleString()} kg MS/ha.`);
    }, 1000);
  };

  // Guardar cambios de edición / muestreo de la parcela
  const handleSaveParcelSample = () => {
    if (!selectedParcel) return;

    setFarm(prev => ({
      ...prev,
      pastures: prev.pastures.map(pasture => {
        if (pasture.id !== selectedParcel.pastureId) return pasture;
        return {
          ...pasture,
          parcels: pasture.parcels.map(p => {
            if (p.id !== selectedParcel.id) return p;
            return {
              ...p,
              code: manualParcelCode.trim() || p.code,
              biomassMS: Number(manualMSValue),
              grassHeightCm: Number(manualGrassHeight),
              dryMatterPercent: Number(manualDryMatterPct),
              samplePhotoUrl: samplePhotoPreview,
              sampleDate: new Date().toISOString().split('T')[0],
              notes: sampleNotes
            };
          })
        };
      }),
      updatedAt: new Date().toISOString()
    }));

    setIsSamplingModalOpen(false);
    showNotification(`💾 Parcela "${manualParcelCode || selectedParcel.code}" actualizada.`);
  };

  // Reiniciar demo
  const handleResetToDemo = () => {
    if (confirm('¿Deseas reiniciar los datos a la Estancia Sujalito de demostración?')) {
      setFarm(INITIAL_FARM);
      localStorage.setItem('aristeus_farm_data', JSON.stringify(INITIAL_FARM));
      setSelectedPastureId('pasture-01');
      showNotification('🔄 Datos reiniciados a la Estancia Sujalito.');
    }
  };

  // Métricas
  const totalParcelsCount = selectedPasture?.parcels?.length || 0;
  const avgBiomass = totalParcelsCount > 0
    ? Math.round(selectedPasture.parcels.reduce((acc, p) => acc + p.biomassMS, 0) / totalParcelsCount)
    : selectedPasture?.defaultBiomassMS || 0;

  const totalBiomassTon = Math.round((avgBiomass * (selectedPasture?.areaHa || 1)) / 1000);
  const estimatedGrazingDays = Math.max(1, Math.round((avgBiomass * (selectedPasture?.areaHa || 1)) / (50 * 12)));

  if (!mounted) {
    return (
      <div className="min-h-[500px] flex items-center justify-center glass rounded-2xl p-8">
        <div className="text-center space-y-4">
          <div className="w-12 h-12 border-4 border-aristeus-green border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="font-heading font-semibold text-text-primary">Cargando sistema geoespacial de la finca...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full space-y-6">
      {/* Notificación flotante */}
      {notification && (
        <div className="fixed top-24 right-6 z-[9999] bg-aristeus-navy text-text-inverse px-5 py-3 rounded-xl shadow-2xl border border-aristeus-green flex items-center gap-3 animate-fade-in">
          <span className="text-aristeus-green text-lg">●</span>
          <span className="text-sm font-medium">{notification}</span>
        </div>
      )}

      {/* Cabecera Principal */}
      <div className="glass rounded-2xl p-4 sm:p-6 flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="px-3 py-1 rounded-full text-xs font-data bg-aristeus-navy text-aristeus-green font-semibold uppercase tracking-wider">
              GrassGauge Pro
            </span>
            <span className="text-xs text-text-secondary font-data">
              {farm.locationName}
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-heading font-bold text-text-primary mt-1">
            {farm.name}
          </h1>
          <p className="text-sm text-text-secondary">
            Dibujo de polígonos con cursor para perímetros, potreros y parcelas personalizadas
          </p>
        </div>

        {/* Botones de acción superior */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-3 w-full lg:w-auto">
          <button
            onClick={() => setIsDbModalOpen(true)}
            className="px-3.5 py-2 rounded-xl text-xs sm:text-sm font-medium glass hover:bg-bg-secondary text-text-primary transition-smooth flex items-center gap-2"
          >
            <svg className="w-4 h-4 text-aristeus-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" />
            </svg>
            <span>Ver SQL / JSON</span>
          </button>

          <button
            onClick={handleResetToDemo}
            className="px-3.5 py-2 rounded-xl text-xs sm:text-sm font-medium glass hover:bg-bg-secondary text-text-secondary transition-smooth"
          >
            Reiniciar Demo
          </button>

          <a
            href="/mi-finca"
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 rounded-xl text-xs sm:text-sm font-medium bg-aristeus-navy hover:bg-aristeus-secondary text-text-inverse transition-smooth flex items-center gap-2 shadow-md"
          >
            <svg className="w-4 h-4 text-aristeus-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            <span>Abrir en Nueva Ventana</span>
          </a>
        </div>
      </div>

      {/* Barra de Herramientas de Dibujo y Edición */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* HU-1: Perímetro y Potreros con Cursor */}
        <div className="glass rounded-2xl p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary font-data">
                HU-1: Perímetro & Potreros
              </span>
              {(drawMode === 'perimeter' || drawMode === 'pasture') && (
                <span className="animate-pulse flex h-2 w-2 rounded-full bg-red-500"></span>
              )}
            </div>
            <p className="text-xs text-text-secondary mb-3">
              {drawMode === 'perimeter'
                ? 'Haga clic en el mapa para marcar los vértices del perímetro.'
                : drawMode === 'pasture'
                ? 'Haga clic en el mapa para delimitar el potrero con el cursor.'
                : 'Defina los límites de la finca o cree nuevos potreros.'}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {drawMode === 'none' ? (
              <>
                <button
                  onClick={() => { setDrawMode('perimeter'); setDraftPoints([]); }}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium bg-aristeus-navy text-text-inverse hover:bg-aristeus-secondary transition-smooth flex items-center gap-1.5"
                >
                  <svg className="w-3.5 h-3.5 text-aristeus-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  <span>Dibujar Perímetro</span>
                </button>
                <button
                  onClick={() => { setDrawMode('pasture'); setDraftPoints([]); }}
                  className="px-3 py-1.5 rounded-lg text-xs font-medium glass hover:bg-bg-secondary text-text-primary transition-smooth flex items-center gap-1.5"
                >
                  <svg className="w-3.5 h-3.5 text-aristeus-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                  </svg>
                  <span>+ Nuevo Potrero</span>
                </button>
              </>
            ) : (drawMode === 'perimeter' || drawMode === 'pasture') ? (
              <div className="w-full space-y-2">
                <div className="flex items-center justify-between text-xs text-text-primary bg-mineral-white/50 p-2 rounded-lg">
                  <span>Vértices: <strong>{draftPoints.length}</strong></span>
                  <div className="flex gap-2">
                    <button
                      onClick={handleUndoLastPoint}
                      disabled={draftPoints.length === 0}
                      className="text-amber-600 hover:underline disabled:opacity-30"
                    >
                      Deshacer
                    </button>
                    <button
                      onClick={() => { setDrawMode('none'); setDraftPoints([]); }}
                      className="text-red-500 hover:underline"
                    >
                      Cancelar
                    </button>
                  </div>
                </div>

                {drawMode === 'pasture' && (
                  <input
                    type="text"
                    placeholder="Nombre ej: Potrero Este"
                    value={newPastureName}
                    onChange={(e) => setNewPastureName(e.target.value)}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-border-subtle bg-bg-card text-text-primary focus:outline-none focus:ring-2 focus:ring-aristeus-green"
                  />
                )}

                <button
                  onClick={drawMode === 'perimeter' ? handleSavePerimeter : handleSaveNewPasture}
                  disabled={draftPoints.length < 3}
                  className="w-full py-1.5 rounded-lg text-xs font-semibold bg-aristeus-green text-text-inverse disabled:opacity-50 hover:brightness-110 transition-smooth"
                >
                  Guardar ({draftPoints.length} vértices)
                </button>
              </div>
            ) : null}
          </div>
        </div>

        {/* HU-3: Dibujo Manual de Parcelas con Vértices */}
        <div className="glass rounded-2xl p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary font-data">
                HU-3: Dibujar Parcelas a Mano
              </span>
              {drawMode === 'parcel' && (
                <span className="animate-pulse flex h-2 w-2 rounded-full bg-emerald-500"></span>
              )}
            </div>
            <p className="text-xs text-text-secondary mb-3">
              {drawMode === 'parcel'
                ? `Haga clic en el mapa para marcar los vértices de la parcela en ${selectedPasture?.name}.`
                : `Potrero activo: ${selectedPasture?.name || 'Ninguno'}. Dibuje parcelas personalizadas con el cursor.`}
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {drawMode === 'none' ? (
              <>
                <button
                  onClick={() => { setDrawMode('parcel'); setDraftPoints([]); }}
                  className="px-3.5 py-1.5 rounded-lg text-xs font-medium bg-aristeus-green text-text-inverse hover:brightness-110 transition-smooth flex items-center gap-1.5"
                >
                  <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
                  </svg>
                  <span>+ Dibujar Parcela con Cursor</span>
                </button>

                {totalParcelsCount > 0 && (
                  <button
                    onClick={() => handleClearAllParcels(selectedPasture.id)}
                    className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-red-500 hover:bg-red-50 transition-smooth"
                    title="Borrar todas las parcelas de este potrero para redibujar"
                  >
                    Borrar Todas
                  </button>
                )}
              </>
            ) : drawMode === 'parcel' ? (
              <div className="w-full space-y-2">
                <div className="flex items-center justify-between text-xs text-text-primary bg-mineral-white/50 p-2 rounded-lg">
                  <span>Vértices de Parcela: <strong>{draftPoints.length}</strong></span>
                  <div className="flex gap-2">
                    <button
                      onClick={handleUndoLastPoint}
                      disabled={draftPoints.length === 0}
                      className="text-amber-600 hover:underline disabled:opacity-30"
                    >
                      Deshacer
                    </button>
                    <button
                      onClick={() => { setDrawMode('none'); setDraftPoints([]); }}
                      className="text-red-500 hover:underline"
                    >
                      Cancelar
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <input
                    type="text"
                    placeholder="Código/Nombre (ej: Parcela A1)"
                    value={newParcelCode}
                    onChange={(e) => setNewParcelCode(e.target.value)}
                    className="w-full px-2.5 py-1.5 text-xs rounded-lg border border-border-subtle bg-bg-card text-text-primary focus:outline-none focus:ring-2 focus:ring-aristeus-green"
                  />
                  <input
                    type="number"
                    placeholder="MS kg/ha (ej: 2200)"
                    value={newParcelMS}
                    onChange={(e) => setNewParcelMS(Number(e.target.value))}
                    className="w-full px-2.5 py-1.5 text-xs font-data rounded-lg border border-border-subtle bg-bg-card text-text-primary focus:outline-none focus:ring-2 focus:ring-aristeus-green"
                  />
                </div>

                <button
                  onClick={handleSaveDrawnParcel}
                  disabled={draftPoints.length < 3}
                  className="w-full py-1.5 rounded-lg text-xs font-semibold bg-aristeus-navy text-text-inverse disabled:opacity-50 hover:bg-aristeus-secondary transition-smooth"
                >
                  Guardar Parcela ({draftPoints.length} vértices)
                </button>
              </div>
            ) : null}
          </div>
        </div>

        {/* HU-4: Visualización Heatmap & Capas */}
        <div className="glass rounded-2xl p-4 flex flex-col justify-between">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary font-data">
              HU-4: Visualización Heatmap
            </span>
            <p className="text-xs text-text-secondary mt-1 mb-3">
              Gradiente cromático de Materia Seca en las parcelas dibujadas.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setViewMode('heatmap')}
              className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-smooth ${
                viewMode === 'heatmap'
                  ? 'bg-aristeus-green text-text-inverse'
                  : 'glass text-text-secondary hover:text-text-primary'
              }`}
            >
              Heatmap Biomasa
            </button>
            <button
              onClick={() => setViewMode('pastures')}
              className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-smooth ${
                viewMode === 'pastures'
                  ? 'bg-aristeus-navy text-text-inverse'
                  : 'glass text-text-secondary hover:text-text-primary'
              }`}
            >
              Solo Potreros
            </button>
            <button
              onClick={() => setMapLayer(mapLayer === 'satellite' ? 'dark' : 'satellite')}
              className="px-3 py-1.5 rounded-lg text-xs font-medium glass text-text-primary hover:bg-bg-secondary"
            >
              {mapLayer === 'satellite' ? '🛰️ Satélite' : '🌙 Oscuro'}
            </button>
          </div>
        </div>
      </div>

      {/* Grid Principal: Mapa y Panel Lateral de Inspección / Edición */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Contenedor del Mapa Leaflet Interactivo */}
        <div className="lg:col-span-3 glass rounded-2xl p-2 relative overflow-hidden flex flex-col">
          {/* Leyenda flotante de Materia Seca */}
          <div className="absolute top-4 right-4 z-[500] glass rounded-xl p-3 shadow-lg max-w-xs pointer-events-auto">
            <p className="text-[11px] font-heading font-semibold text-text-primary mb-1.5">
              Escala de Materia Seca (MS)
            </p>
            <div className="space-y-1 text-[10px] font-data">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-emerald-600"></span>
                <span>&gt; 2,200 kg MS/ha (Excelente)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-lime-500"></span>
                <span>1,600 - 2,200 kg MS/ha (Óptima)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-amber-400"></span>
                <span>1,000 - 1,600 kg MS/ha (Media)</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-sm bg-red-500"></span>
                <span>&lt; 1,000 kg MS/ha (Crítica)</span>
              </div>
            </div>
          </div>

          {/* Banner de Modo Dibujo Activo */}
          {drawMode !== 'none' && (
            <div className="absolute top-4 left-4 z-[500] bg-aristeus-navy/95 text-text-inverse px-4 py-2 rounded-xl shadow-xl border border-aristeus-green text-xs flex items-center gap-2">
              <span className="animate-spin text-aristeus-green">✏️</span>
              <span>
                {drawMode === 'perimeter' && 'Marcando perímetro de la finca con clics...'}
                {drawMode === 'pasture' && 'Delimitando nuevo potrero con clics...'}
                {drawMode === 'parcel' && `Dibujando parcela en ${selectedPasture?.name}...`}
              </span>
            </div>
          )}

          {/* Mapa Leaflet */}
          <div className="w-full h-[540px] sm:h-[620px] rounded-xl overflow-hidden relative">
            <MapContainer
              center={farm.center as LatLngExpression}
              zoom={DEFAULT_ZOOM}
              style={{ width: '100%', height: '100%' }}
              className="z-10"
            >
              <ChangeView center={farm.center} zoom={DEFAULT_ZOOM} />
              <MapClickHandler drawMode={drawMode} onAddPoint={handleAddDraftPoint} />

              {/* Capa de Tiles Satelitales / Base */}
              {mapLayer === 'satellite' ? (
                <TileLayer
                  attribution='&copy; <a href="https://www.esri.com/">Esri</a>, Earthstar Geographics'
                  url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
                  maxZoom={19}
                />
              ) : (
                <TileLayer
                  attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                  url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                  maxZoom={19}
                />
              )}

              {/* Imagen Overlay de Sujalito */}
              <ImageOverlay
                url="/img/sujalito-satellite.png"
                bounds={[
                  [-17.3950, -63.3050],
                  [-17.4320, -63.2550]
                ]}
                opacity={0.35}
              />

              {/* Perímetro de la Finca */}
              {farm.perimeterCoordinates && farm.perimeterCoordinates.length >= 3 && (
                <Polygon
                  positions={farm.perimeterCoordinates as LatLngExpression[]}
                  pathOptions={{
                    color: '#0B2341',
                    weight: 3,
                    dashArray: '6, 6',
                    fillColor: '#0B2341',
                    fillOpacity: 0.05
                  }}
                >
                  <Tooltip permanent={false} direction="center">
                    <span className="font-heading font-semibold text-xs">Perímetro: {farm.name}</span>
                  </Tooltip>
                </Polygon>
              )}

              {/* Polígonos de Potreros */}
              {farm.pastures.map((pasture) => {
                const isSelected = pasture.id === selectedPastureId;
                const hasParcels = pasture.parcels && pasture.parcels.length > 0;

                return (
                  <React.Fragment key={pasture.id}>
                    <Polygon
                      positions={pasture.coordinates as LatLngExpression[]}
                      pathOptions={{
                        color: isSelected ? '#6BA539' : '#FFFFFF',
                        weight: isSelected ? 3.5 : 2,
                        fillColor: pasture.color || '#355E3B',
                        fillOpacity: (viewMode === 'heatmap' && hasParcels) ? 0.15 : 0.45
                      }}
                      eventHandlers={{
                        click: () => {
                          if (drawMode === 'none') {
                            setSelectedPastureId(pasture.id);
                          }
                        }
                      }}
                    >
                      {/* Tooltip si no tiene parcelas */}
                      <Tooltip sticky direction="top" opacity={0.95}>
                        <div className="p-1 text-xs font-sans text-aristeus-navy">
                          <p className="font-bold">{pasture.name}</p>
                          <p className="font-data text-[11px] text-emerald-700">
                            MS Estimada: {pasture.defaultBiomassMS.toLocaleString()} kg/ha
                          </p>
                          <p className="text-[10px] text-gray-600">{pasture.areaHa} ha • {pasture.grassType}</p>
                        </div>
                      </Tooltip>
                    </Polygon>

                    {/* Parcelas Dibujadas a Mano dentro del Potrero */}
                    {viewMode !== 'pastures' && pasture.parcels?.map((parcel) => {
                      const colorInfo = getBiomassColor(parcel.biomassMS);
                      const isParcelSelected = selectedParcel?.id === parcel.id;

                      return (
                        <Polygon
                          key={parcel.id}
                          positions={parcel.coordinates as LatLngExpression[]}
                          pathOptions={{
                            color: isParcelSelected ? '#FFFFFF' : colorInfo.stroke,
                            weight: isParcelSelected ? 2.5 : 1.5,
                            fillColor: colorInfo.fill,
                            fillOpacity: 0.65
                          }}
                          eventHandlers={{
                            click: () => {
                              setSelectedPastureId(pasture.id);
                              handleOpenSampling(parcel);
                            }
                          }}
                        >
                          <Tooltip direction="center" opacity={0.95}>
                            <div className="p-1 text-center font-sans">
                              <p className="font-heading font-bold text-xs text-aristeus-navy">{parcel.code}</p>
                              <p className="font-data font-bold text-xs text-emerald-800">
                                {parcel.biomassMS.toLocaleString()} <span className="text-[10px]">kg MS/ha</span>
                              </p>
                              {parcel.samplePhotoUrl && (
                                <p className="text-[9px] text-green-700">📷 Con foto</p>
                              )}
                              <p className="text-[9px] text-gray-500">Click para editar/eliminar</p>
                            </div>
                          </Tooltip>
                        </Polygon>
                      );
                    })}
                  </React.Fragment>
                );
              })}

              {/* Trazo preliminar al dibujar con cursor */}
              {drawMode !== 'none' && draftPoints.length > 0 && (
                <>
                  <Polyline
                    positions={draftPoints as LatLngExpression[]}
                    pathOptions={{ color: '#E05345', weight: 3, dashArray: '4, 4' }}
                  />
                  {draftPoints.map((pt, idx) => (
                    <Marker key={idx} position={pt as LatLngExpression} icon={customIcon}>
                      <Tooltip permanent direction="right">
                        <span className="font-data text-[10px]">V{idx + 1}</span>
                      </Tooltip>
                    </Marker>
                  ))}
                </>
              )}
            </MapContainer>
          </div>
        </div>

        {/* Panel Lateral: Lista de Parcelas Dibujadas, Métricas y Acciones */}
        <div className="glass rounded-2xl p-6 space-y-6 flex flex-col justify-between">
          <div className="space-y-5">
            {/* Cabecera del Potrero */}
            <div className="border-b border-border-subtle pb-4 flex items-start justify-between">
              <div>
                <span className="text-xs font-semibold text-text-secondary uppercase tracking-wider font-data">
                  Potrero Activo
                </span>
                <h2 className="font-heading font-bold text-xl text-text-primary mt-1">
                  {selectedPasture?.name}
                </h2>
                <span className="text-xs text-text-secondary">
                  {selectedPasture?.grassType} • {selectedPasture?.areaHa} ha
                </span>
              </div>
              <button
                onClick={() => handleDeletePasture(selectedPasture.id)}
                className="text-text-secondary hover:text-red-500 p-1"
                title="Eliminar este potrero"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>

            {/* Métricas de Biomasa */}
            <div className="space-y-3">
              <div className="p-3.5 rounded-xl bg-bg-card/70 border border-border-subtle">
                <span className="text-xs text-text-secondary">Materia Seca Promedio</span>
                <div className="flex items-baseline justify-between mt-1">
                  <span className="font-data text-2xl font-bold text-aristeus-green">
                    {avgBiomass.toLocaleString()}
                  </span>
                  <span className="text-xs font-data text-text-secondary">kg MS / ha</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="p-3 rounded-xl bg-bg-card/70 border border-border-subtle">
                  <span className="text-[11px] text-text-secondary">Biomasa Total</span>
                  <p className="font-data text-base font-bold text-text-primary mt-0.5">
                    ~{totalBiomassTon} Ton MS
                  </p>
                </div>
                <div className="p-3 rounded-xl bg-bg-card/70 border border-border-subtle">
                  <span className="text-[11px] text-text-secondary">Días Pastoreo</span>
                  <p className="font-data text-base font-bold text-aristeus-green mt-0.5">
                    ~{estimatedGrazingDays} días
                  </p>
                </div>
              </div>
            </div>

            {/* Lista de Parcelas Dibujadas con Acciones de Edición/Eliminación */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-text-secondary">
                <span className="font-semibold">Parcelas Dibujadas ({totalParcelsCount})</span>
                <button
                  onClick={() => { setDrawMode('parcel'); setDraftPoints([]); }}
                  className="text-aristeus-green hover:underline font-medium"
                >
                  + Nueva Parcela
                </button>
              </div>

              {totalParcelsCount === 0 ? (
                <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs space-y-2">
                  <p className="font-semibold text-amber-700">Sin parcelas dibujadas</p>
                  <p className="text-text-secondary">
                    Haz clic en <strong>"+ Dibujar Parcela con Cursor"</strong> para trazar con clics la forma exacta de tus parcelas o sectores de muestreo.
                  </p>
                </div>
              ) : (
                <div className="max-h-52 overflow-y-auto space-y-2 pr-1 text-xs">
                  {selectedPasture.parcels.map(p => {
                    const cInfo = getBiomassColor(p.biomassMS);
                    return (
                      <div
                        key={p.id}
                        className="p-2.5 rounded-xl bg-bg-card hover:bg-bg-secondary border border-border-subtle transition-smooth flex items-center justify-between group"
                      >
                        <div
                          className="flex items-center gap-2 cursor-pointer flex-1"
                          onClick={() => handleOpenSampling(p)}
                        >
                          <span className={`w-2.5 h-2.5 rounded-full ${cInfo.bgClass}`}></span>
                          <div>
                            <span className="font-heading font-semibold text-text-primary block">{p.code}</span>
                            <span className="text-[10px] text-text-secondary font-data">{p.coordinates.length} vértices</span>
                          </div>
                          {p.samplePhotoUrl && <span title="Tiene foto de muestra">📷</span>}
                        </div>

                        <div className="flex items-center gap-2">
                          <span className="font-data font-bold text-text-primary text-right">
                            {p.biomassMS} <span className="text-[10px] text-text-secondary">kg/ha</span>
                          </span>
                          <button
                            onClick={() => handleOpenSampling(p)}
                            className="p-1 text-text-secondary hover:text-aristeus-green"
                            title="Editar datos y foto"
                          >
                            ✏️
                          </button>
                          <button
                            onClick={() => handleDeleteParcel(p.id, selectedPasture.id)}
                            className="p-1 text-text-secondary hover:text-red-500"
                            title="Eliminar parcela"
                          >
                            🗑️
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Selector de Potrero */}
          <div className="pt-4 border-t border-border-subtle">
            <label className="text-xs text-text-secondary block mb-1.5">Cambiar Potrero Activo:</label>
            <select
              value={selectedPastureId || ''}
              onChange={(e) => setSelectedPastureId(e.target.value)}
              className="w-full px-3 py-2 text-xs rounded-xl border border-border-subtle bg-bg-card text-text-primary focus:outline-none focus:ring-2 focus:ring-aristeus-green"
            >
              {farm.pastures.map(p => (
                <option key={p.id} value={p.id}>{p.name} ({p.areaHa} ha)</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Modal de Muestreo, Edición y Eliminación de Parcela */}
      {isSamplingModalOpen && selectedParcel && (
        <div className="fixed inset-0 z-[9999] bg-aristeus-navy/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass bg-bg-card rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-border-subtle space-y-5 animate-fade-in">
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
              <div>
                <span className="text-xs font-data text-aristeus-green uppercase tracking-wider font-semibold">
                  Muestreo & Edición de Parcela
                </span>
                <h3 className="font-heading font-bold text-lg text-text-primary">
                  {selectedParcel.code}
                </h3>
              </div>
              <button
                onClick={() => setIsSamplingModalOpen(false)}
                className="text-text-secondary hover:text-text-primary text-xl font-bold p-1"
              >
                ✕
              </button>
            </div>

            {/* Código / Nombre de la parcela editable */}
            <div>
              <label className="text-xs font-medium text-text-primary block mb-1">Nombre / Identificador de la Parcela</label>
              <input
                type="text"
                value={manualParcelCode}
                onChange={(e) => setManualParcelCode(e.target.value)}
                className="w-full px-3 py-2 text-xs rounded-xl border border-border-subtle bg-bg-card text-text-primary focus:outline-none focus:ring-2 focus:ring-aristeus-green"
              />
            </div>

            {/* Subida de Fotografía */}
            <div className="space-y-2">
              <label className="text-xs font-medium text-text-primary block">
                Fotografía del Pasto (Muestra)
              </label>
              
              <div className="border-2 border-dashed border-border-subtle rounded-xl p-4 text-center hover:border-aristeus-green transition-smooth bg-bg-secondary/40">
                {samplePhotoPreview ? (
                  <div className="space-y-2">
                    <img
                      src={samplePhotoPreview}
                      alt="Muestra de pasto"
                      className="max-h-40 mx-auto rounded-lg object-cover shadow-sm"
                    />
                    <button
                      type="button"
                      onClick={() => setSamplePhotoPreview('')}
                      className="text-xs text-red-500 hover:underline"
                    >
                      Eliminar foto
                    </button>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <svg className="w-8 h-8 text-text-secondary mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                    </svg>
                    <p className="text-xs text-text-secondary">
                      Arrastra o sube una fotografía del forraje para registrar la muestra
                    </p>
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handlePhotoUpload}
                      className="text-xs text-text-secondary file:mr-2 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-xs file:bg-aristeus-green file:text-text-inverse cursor-pointer"
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Ingreso manual y simulación ML */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <label className="text-xs font-medium text-text-primary">
                  Valores de Materia Seca (Manual o ML)
                </label>
                <button
                  type="button"
                  onClick={handleSimulateML}
                  disabled={isSimulatingML}
                  className="px-2.5 py-1 rounded-lg text-xs font-medium bg-aristeus-secondary/20 hover:bg-aristeus-secondary/30 text-aristeus-secondary transition-smooth flex items-center gap-1"
                >
                  {isSimulatingML ? (
                    <>
                      <span className="w-3 h-3 border-2 border-aristeus-secondary border-t-transparent rounded-full animate-spin"></span>
                      <span>Analizando...</span>
                    </>
                  ) : (
                    <>
                      <span>✨</span>
                      <span>Calcular con Modelo ML</span>
                    </>
                  )}
                </button>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-[11px] text-text-secondary block mb-1">Materia Seca</label>
                  <div className="relative">
                    <input
                      type="number"
                      value={manualMSValue}
                      onChange={(e) => setManualMSValue(Number(e.target.value))}
                      className="w-full px-3 py-2 text-xs font-data rounded-xl border border-border-subtle bg-bg-card text-text-primary focus:outline-none focus:ring-2 focus:ring-aristeus-green font-bold"
                    />
                    <span className="absolute right-2 top-2 text-[10px] text-text-secondary">kg/ha</span>
                  </div>
                </div>

                <div>
                  <label className="text-[11px] text-text-secondary block mb-1">% Mat. Seca</label>
                  <div className="relative">
                    <input
                      type="number"
                      value={manualDryMatterPct}
                      onChange={(e) => setManualDryMatterPct(Number(e.target.value))}
                      className="w-full px-3 py-2 text-xs font-data rounded-xl border border-border-subtle bg-bg-card text-text-primary focus:outline-none focus:ring-2 focus:ring-aristeus-green"
                    />
                    <span className="absolute right-2 top-2 text-[10px] text-text-secondary">%</span>
                  </div>
                </div>

                <div>
                  <label className="text-[11px] text-text-secondary block mb-1">Altura Pasto</label>
                  <div className="relative">
                    <input
                      type="number"
                      value={manualGrassHeight}
                      onChange={(e) => setManualGrassHeight(Number(e.target.value))}
                      className="w-full px-3 py-2 text-xs font-data rounded-xl border border-border-subtle bg-bg-card text-text-primary focus:outline-none focus:ring-2 focus:ring-aristeus-green"
                    />
                    <span className="absolute right-2 top-2 text-[10px] text-text-secondary">cm</span>
                  </div>
                </div>
              </div>

              {/* Vista previa de color */}
              <div className="p-2.5 rounded-xl bg-bg-secondary/40 flex items-center justify-between text-xs">
                <span className="text-text-secondary">Color resultante:</span>
                <span className="font-semibold flex items-center gap-1.5" style={{ color: getBiomassColor(manualMSValue).fill }}>
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: getBiomassColor(manualMSValue).fill }}></span>
                  {getBiomassColor(manualMSValue).label}
                </span>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-medium text-text-primary block">Observaciones</label>
              <textarea
                value={sampleNotes}
                onChange={(e) => setSampleNotes(e.target.value)}
                placeholder="Observaciones de campo..."
                rows={2}
                className="w-full px-3 py-2 text-xs rounded-xl border border-border-subtle bg-bg-card text-text-primary focus:outline-none focus:ring-2 focus:ring-aristeus-green resize-none"
              />
            </div>

            {/* Acciones */}
            <div className="flex items-center justify-between pt-3 border-t border-border-subtle">
              <button
                type="button"
                onClick={() => handleDeleteParcel(selectedParcel.id, selectedParcel.pastureId)}
                className="text-xs font-medium text-red-500 hover:underline flex items-center gap-1"
              >
                <span>🗑️ Eliminar Parcela</span>
              </button>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setIsSamplingModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-medium glass hover:bg-bg-secondary text-text-secondary transition-smooth"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleSaveParcelSample}
                  className="px-5 py-2 rounded-xl text-xs font-semibold bg-aristeus-green hover:brightness-110 text-text-inverse transition-smooth shadow-md"
                >
                  Guardar Cambios
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal SQL / JSON */}
      {isDbModalOpen && (
        <div className="fixed inset-0 z-[9999] bg-aristeus-navy/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass bg-bg-card rounded-2xl max-w-2xl w-full p-6 shadow-2xl border border-border-subtle space-y-4 animate-fade-in">
            <div className="flex items-center justify-between border-b border-border-subtle pb-3">
              <div>
                <span className="text-xs font-data text-aristeus-green uppercase tracking-wider font-semibold">
                  Integración con Base de Datos
                </span>
                <h3 className="font-heading font-bold text-lg text-text-primary">
                  Estructura SQL / JSON de Mi Finca
                </h3>
              </div>
              <button
                onClick={() => setIsDbModalOpen(false)}
                className="text-text-secondary hover:text-text-primary text-xl font-bold p-1"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-text-secondary">
              Estructura SQL y JSON con todos los vértices de polígonos dibujados a mano:
            </p>

            <div className="space-y-3">
              <div>
                <span className="text-xs font-semibold text-text-primary font-data">Schema Relacional SQL:</span>
                <pre className="mt-1 p-3 rounded-xl bg-technical-graphite text-mineral-white font-data text-[11px] overflow-x-auto max-h-44">
{`-- 1. Tabla de Fincas y Perímetro
CREATE TABLE fincas (
  id VARCHAR(64) PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL,
  ubicacion VARCHAR(120),
  perimetro_coordenadas JSON, -- Vértices dibujados [[lat, lng], ...]
  area_ha DECIMAL(10,2)
);

-- 2. Tabla de Potreros
CREATE TABLE potreros (
  id VARCHAR(64) PRIMARY KEY,
  finca_id VARCHAR(64) REFERENCES fincas(id) ON DELETE CASCADE,
  nombre VARCHAR(120) NOT NULL,
  coordenadas JSON NOT NULL, -- Polígono del potrero
  biomasa_estimada DECIMAL(10,2)
);

-- 3. Tabla de Parcelas Dibujadas a Mano
CREATE TABLE parcelas_muestreo (
  id VARCHAR(64) PRIMARY KEY,
  potrero_id VARCHAR(64) REFERENCES potreros(id) ON DELETE CASCADE,
  codigo VARCHAR(30) NOT NULL,
  coordenadas JSON NOT NULL, -- Vértices personalizados
  materia_seca_kg_ha DECIMAL(10,2),
  foto_url TEXT,
  fecha_muestreo DATE
);`}
                </pre>
              </div>

              <div>
                <span className="text-xs font-semibold text-text-primary font-data">JSON Actual con Polígonos Dibujados:</span>
                <pre className="mt-1 p-3 rounded-xl bg-technical-graphite text-aristeus-green font-data text-[11px] overflow-x-auto max-h-36">
                  {JSON.stringify(farm, null, 2)}
                </pre>
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-border-subtle">
              <button
                type="button"
                onClick={() => {
                  navigator.clipboard.writeText(JSON.stringify(farm, null, 2));
                  showNotification('📋 JSON copiado al portapapeles.');
                }}
                className="px-4 py-2 rounded-xl text-xs font-medium bg-aristeus-navy text-text-inverse hover:bg-aristeus-secondary transition-smooth"
              >
                Copiar JSON
              </button>
              <button
                type="button"
                onClick={() => setIsDbModalOpen(false)}
                className="px-4 py-2 rounded-xl text-xs font-medium glass hover:bg-bg-secondary text-text-primary transition-smooth"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
