

import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch

# Configuración - formato horizontal
plt.rcParams['figure.figsize'] = (24, 16) # Más ancho que alto
plt.rcParams['font.family'] = 'sans-serif'

# Colores
COLORS = {
    'entrada': '#d4e6f1',
    'backbone': '#d5f5e3',
    'fusion': '#fcf3cf',
    'mamba': '#fad7a0',
    'heads': '#e8daef',
    'output': '#f9e79f',
    'loss': '#f1948a'
}

def crear_diagrama_horizontal():
    """Versión HORIZONTAL con textos en línea"""
    fig, ax = plt.subplots(1, 1, figsize=(24, 16))
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 16)
    ax.axis('off')
    
    # Título
    ax.text(12, 15.5, 'Diagrama de Flujo Detallado - Modelo CSIRO Biomasa', 
            ha='center', fontsize=16, fontweight='bold')
    
    # === NIVEL 1: ENTRADA DUAL (Y=14) ===
    ax.text(12, 14.2, 'ENTRADA DUAL', ha='center', fontsize=12, fontweight='bold')
    
    # Cámara Izquierda - TEXTO HORIZONTAL
    izq = FancyBboxPatch((4, 13.0), 5, 1.2, boxstyle="round,pad=0.2", 
                         facecolor=COLORS['entrada'], edgecolor='black', linewidth=2)
    ax.add_patch(izq)
    ax.text(6.5, 13.6, 'Cámara Izquierda', ha='center', va='center', fontsize=10, fontweight='bold')
    
    # Cámara Derecha
    der = FancyBboxPatch((15, 13.0), 5, 1.2, boxstyle="round,pad=0.2", 
                         facecolor=COLORS['entrada'], edgecolor='black', linewidth=2)
    ax.add_patch(der)
    ax.text(17.5, 13.6, 'Cámara Derecha', ha='center', va='center', fontsize=10, fontweight='bold')
    
    # Aumentos
    ax.text(6.5, 12.2, 'Albumentations', ha='center', fontsize=9, style='italic')
    ax.text(17.5, 12.2, 'Albumentations', ha='center', fontsize=9, style='italic')
    
    # Flechas
    ax.annotate('', xy=(6.5, 11.5), xytext=(6.5, 12.5), arrowprops=dict(arrowstyle='->', lw=2))
    ax.annotate('', xy=(17.5, 11.5), xytext=(17.5, 12.5), arrowprops=dict(arrowstyle='->', lw=2))
    
    # === NIVEL 2: BACKBONE (Y=10.5) ===
    ax.text(12, 11.0, 'BACKBONE', ha='center', fontsize=12, fontweight='bold')
    
    # Backbone Izquierdo - TEXTO HORIZONTAL EN MÚLTIPLES LÍNEAS
    bb_izq = FancyBboxPatch((2, 9.0), 7, 1.8, boxstyle="round,pad=0.2", 
                            facecolor=COLORS['backbone'], edgecolor='black', linewidth=2)
    ax.add_patch(bb_izq)
    ax.text(5.5, 10.2, 'DINOv3-ViT-L/16 + LoRA', ha='center', va='center', fontsize=9, fontweight='bold')
    ax.text(5.5, 9.6, 'k_proj, v_proj, q_proj, o_proj', ha='center', fontsize=8)
    ax.text(5.5, 9.0, 'con adaptadores LoRA', ha='center', fontsize=8, style='italic')
    
    # Backbone Derecho
    bb_der = FancyBboxPatch((15, 9.0), 7, 1.8, boxstyle="round,pad=0.2", 
                            facecolor=COLORS['backbone'], edgecolor='black', linewidth=2)
    ax.add_patch(bb_der)
    ax.text(18.5, 10.2, 'DINOv3-ViT-L/16 + LoRA', ha='center', va='center', fontsize=9, fontweight='bold')
    ax.text(18.5, 9.6, 'k_proj, v_proj, q_proj, o_proj', ha='center', fontsize=8)
    ax.text(18.5, 9.0, 'con adaptadores LoRA', ha='center', fontsize=8, style='italic')
    
    # Tokens
    ax.text(5.5, 8.0, '[Tokens Izquierdos]', ha='center', fontsize=8)
    ax.text(18.5, 8.0, '[Tokens Derechos]', ha='center', fontsize=8)
    
    # Flechas
    ax.annotate('', xy=(8, 7.5), xytext=(6.5, 8.5), arrowprops=dict(arrowstyle='->', lw=2))
    ax.annotate('', xy=(16, 7.5), xytext=(17.5, 8.5), arrowprops=dict(arrowstyle='->', lw=2))
    
    # === NIVEL 3: SUMA DE TOKENS (Y=6.5) ===
    fusion = FancyBboxPatch((8, 6.0), 8, 1.5, boxstyle="round,pad=0.2", 
                            facecolor=COLORS['fusion'], edgecolor='black', linewidth=2)
    ax.add_patch(fusion)
    ax.text(12, 6.9, 'SUMA DE TOKENS - Fusión Temprana', ha='center', va='center', fontsize=10, fontweight='bold')
    ax.text(12, 6.3, 'Izquierdo + Derecho (element-wise)', ha='center', va='center', fontsize=9)
    
    ax.text(12, 5.0, '[Tokens Fusionados]', ha='center', fontsize=8)
    
    # Flecha
    ax.annotate('', xy=(12, 4.2), xytext=(12, 4.8), arrowprops=dict(arrowstyle='->', lw=2))
    
    # === NIVEL 4: MAMBA (Y=3.5) ===
    ax.text(12, 4.0, 'MAMBA', ha='center', fontsize=12, fontweight='bold')
    
    # Convolución 1D - TEXTO HORIZONTAL
    conv = FancyBboxPatch((2, 2.0), 6, 1.6, boxstyle="round,pad=0.2", 
                          facecolor=COLORS['mamba'], edgecolor='black', linewidth=2)
    ax.add_patch(conv)
    ax.text(5, 3.0, 'Convolución 1D (dwconv)', ha='center', va='center', fontsize=9, fontweight='bold')
    ax.text(5, 2.4, 'Captura relaciones locales', ha='center', fontsize=8)
    ax.text(5, 1.8, 'entre parches', ha='center', fontsize=8)
    
    # Gate
    gate = FancyBboxPatch((9, 2.0), 6, 1.6, boxstyle="round,pad=0.2", 
                          facecolor=COLORS['mamba'], edgecolor='black', linewidth=2)
    ax.add_patch(gate)
    ax.text(12, 3.0, 'GATE', ha='center', va='center', fontsize=10, fontweight='bold')
    ax.text(12, 2.4, 'Selección de información', ha='center', fontsize=8)
    ax.text(12, 1.8, 'Filtro 0-1', ha='center', fontsize=8)
    
    # Estado SSM
    ssm = FancyBboxPatch((16, 2.0), 6, 1.6, boxstyle="round,pad=0.2", 
                         facecolor=COLORS['mamba'], edgecolor='black', linewidth=2)
    ax.add_patch(ssm)
    ax.text(19, 3.0, 'ESTADO SSM', ha='center', va='center', fontsize=9, fontweight='bold')
    ax.text(19, 2.4, 'Mamba - Fusión espacial', ha='center', fontsize=8)
    ax.text(19, 1.8, 'Contexto global y memoria', ha='center', fontsize=8)
    
    # Conexiones horizontales
    ax.annotate('', xy=(8, 2.8), xytext=(5, 2.8), arrowprops=dict(arrowstyle='->', lw=1.5))
    ax.annotate('', xy=(16, 2.8), xytext=(12, 2.8), arrowprops=dict(arrowstyle='->', lw=1.5))
    
    ax.text(12, 0.5, '[Representación Espacial Fusionada]', ha='center', fontsize=8)
    
    # Flecha
    ax.annotate('', xy=(12, -0.2), xytext=(12, 0.3), arrowprops=dict(arrowstyle='->', lw=2))
    
    # === NIVEL 5: CABEZALES DE REGRESIÓN (Y=-1) ===
    ax.text(12, 0, 'CABEZALES DE REGRESIÓN', ha='center', fontsize=11, fontweight='bold')
    
    # Green
    green = FancyBboxPatch((2, -2.0), 6, 1.5, boxstyle="round,pad=0.2", 
                           facecolor=COLORS['heads'], edgecolor='black', linewidth=2)
    ax.add_patch(green)
    ax.text(5, -1.2, 'Head Green', ha='center', va='center', fontsize=9, fontweight='bold')
    ax.text(5, -1.8, 'Softplus - Salida positiva', ha='center', fontsize=8)
    
    # Dead
    dead = FancyBboxPatch((9, -2.0), 6, 1.5, boxstyle="round,pad=0.2", 
                          facecolor=COLORS['heads'], edgecolor='black', linewidth=2)
    ax.add_patch(dead)
    ax.text(12, -1.2, 'Head Dead', ha='center', va='center', fontsize=9, fontweight='bold')
    ax.text(12, -1.8, 'Softplus - Salida positiva', ha='center', fontsize=8)
    
    # Clover
    clover = FancyBboxPatch((16, -2.0), 6, 1.5, boxstyle="round,pad=0.2", 
                            facecolor=COLORS['heads'], edgecolor='black', linewidth=2)
    ax.add_patch(clover)
    ax.text(19, -1.2, 'Head Clover', ha='center', va='center', fontsize=9, fontweight='bold')
    ax.text(19, -1.8, 'Softplus - Salida positiva', ha='center', fontsize=8)
    
    # Conexiones
    ax.annotate('', xy=(5, -2.0), xytext=(12, -0.5), arrowprops=dict(arrowstyle='->', lw=1.5))
    ax.annotate('', xy=(12, -2.0), xytext=(12, -0.5), arrowprops=dict(arrowstyle='->', lw=1.5))
    ax.annotate('', xy=(19, -2.0), xytext=(12, -0.5), arrowprops=dict(arrowstyle='->', lw=1.5))
    
    # Predicciones
    ax.text(5, -3.2, '[Pred Green]', ha='center', fontsize=8)
    ax.text(12, -3.2, '[Pred Dead]', ha='center', fontsize=8)
    ax.text(19, -3.2, '[Pred Clover]', ha='center', fontsize=8)
    
    # Flechas
    ax.annotate('', xy=(7, -4.0), xytext=(5, -3.5), arrowprops=dict(arrowstyle='->', lw=1.5))
    ax.annotate('', xy=(12, -4.0), xytext=(12, -3.5), arrowprops=dict(arrowstyle='->', lw=1.5))
    ax.annotate('', xy=(17, -4.0), xytext=(19, -3.5), arrowprops=dict(arrowstyle='->', lw=1.5))
    
    # === NIVEL 6: PRED TOTAL (Y=-4.5) ===
    total = FancyBboxPatch((8, -5.0), 8, 1.5, boxstyle="round,pad=0.2", 
                           facecolor=COLORS['output'], edgecolor='black', linewidth=2)
    ax.add_patch(total)
    ax.text(12, -4.2, 'PRED TOTAL = Green + Dead + Clover', ha='center', va='center', fontsize=9, fontweight='bold')
    
    # Flecha
    ax.annotate('', xy=(12, -6.0), xytext=(12, -5.5), arrowprops=dict(arrowstyle='->', lw=2))
    
    # === NIVEL 7: TWEEDIE LOSS (Y=-6.5) ===
    loss = FancyBboxPatch((8, -7.0), 8, 1.5, boxstyle="round,pad=0.2", 
                          facecolor=COLORS['loss'], edgecolor='black', linewidth=2)
    ax.add_patch(loss)
    ax.text(12, -6.2, 'TWEEDIE LOSS (p = 1.2)', ha='center', va='center', fontsize=9, fontweight='bold')
    
    # Notas
    ax.text(12, -8.2, 'Retropropagación + Gradient Clipping', ha='center', fontsize=8)
    ax.text(12, -8.7, 'Actualización de EMA (modelo suavizado)', ha='center', fontsize=8, style='italic')
    
    # Leyenda horizontal
    legend_y = -10
    legend_elements = [
        FancyBboxPatch((2, legend_y), 1.8, 0.8, facecolor=COLORS['entrada'], edgecolor='black', label='Entrada'),
        FancyBboxPatch((4, legend_y), 1.8, 0.8, facecolor=COLORS['backbone'], edgecolor='black', label='Backbone'),
        FancyBboxPatch((6, legend_y), 1.8, 0.8, facecolor=COLORS['fusion'], edgecolor='black', label='Fusión'),
        FancyBboxPatch((8, legend_y), 1.8, 0.8, facecolor=COLORS['mamba'], edgecolor='black', label='Mamba'),
        FancyBboxPatch((10, legend_y), 1.8, 0.8, facecolor=COLORS['heads'], edgecolor='black', label='Cabezales'),
        FancyBboxPatch((12, legend_y), 1.8, 0.8, facecolor=COLORS['output'], edgecolor='black', label='Salida'),
        FancyBboxPatch((14, legend_y), 1.8, 0.8, facecolor=COLORS['loss'], edgecolor='black', label='Pérdida')
    ]
    for i, elem in enumerate(legend_elements):
        ax.add_patch(elem)
        ax.text(2.9 + i*2, legend_y+0.4, elem.get_label(), ha='center', va='center', fontsize=8)
    
    ax.set_ylim(-11, 16)
    plt.tight_layout()
    return fig

# Generar y guardar
print("Generando diagrama HORIZONTAL...")
fig = crear_diagrama_horizontal()
plt.savefig('Diagrama_CSIRO_Horizontal.png', dpi=150, bbox_inches='tight', facecolor='white')
plt.close(fig)
print("✓ Diagrama guardado como 'Diagrama_CSIRO_Horizontal.png'")