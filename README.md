# Sistema Domótico Modular con Zephyr RTOS

## Visión del Proyecto

Desarrollo de un sistema domótico modular, robusto y escalable basado en **Zephyr RTOS**. El sistema prioriza la **operación autónoma local** mientras permite acceso remoto opcional. Está diseñado para crecer progresivamente desde un MVP funcional hasta un sistema completo de automatización del hogar.

---

## Principios de Diseño

1. **Autonomía Local Primero**: El sistema funciona completamente sin internet ni cloud
2. **Modularidad**: Componentes independientes que se comunican por interfaces bien definidas
3. **Escalabilidad**: Desde un nodo hasta decenas de dispositivos
4. **Prioridad de Control Físico**: Los botones/controles locales siempre tienen precedencia
5. **Desarrollo Incremental**: Construcción por capas, validando cada etapa

---

## Arquitectura del Sistema
```
┌─────────────────┐
│  Aplicación     │
│     Móvil       │  (Acceso remoto opcional)
└────────┬────────┘
         │
         │ HTTPS/WebSocket
         │
┌────────▼────────┐
│   Backend       │
│   Cloudflare    │  (Acceso remoto, sin IP fija)
└────────┬────────┘
         │
         │ TLS
         │
┌────────▼────────┐
│   Computador    │
│     Local       │  (Gateway, histórico, no crítico)
│   (Servidor)    │
└────────┬────────┘
         │
         │ BLE / USB
         │
┌────────▼────────┐
│     Nodo        │
│   Principal     │  (Hub local, siempre operativo)
│   (Zephyr)      │
└────────┬────────┘
         │
         │ BLE / Sub-GHz
         │
┌────────▼────────┐
│     Nodos       │
│  Secundarios    │  (Sensores, actuadores)
│   (Zephyr)      │
└─────────────────┘
```

---

## Componentes

### 🎯 Nodo Principal (Zephyr RTOS)
**Rol**: Hub central del sistema domótico

- Agrega datos de nodos secundarios
- Controla actuadores localmente
- Mantiene estado actual del sistema (sin histórico)
- Interfaz local: pantalla + botones físicos
- **Opera completamente offline**
- Se comunica con gateway cuando está disponible

### 📡 Nodos Secundarios (Zephyr RTOS)
**Rol**: Dispositivos periféricos de sensado y actuación

- Sensores: temperatura, humedad, movimiento, luminosidad, etc.
- Actuadores: luces, enchufes inteligentes, persianas, etc.
- Diseño de bajo consumo energético
- Comunicación inalámbrica con nodo principal

### 💻 Computador Local (Gateway)
**Rol**: Puente opcional entre sistema local y cloud

- Gateway de comunicación
- Almacenamiento de histórico (opcional)
- API local para integración
- Sincronización con backend remoto
- **No crítico**: sistema funciona sin él

### ☁️ Backend en la Nube (Cloudflare)
**Rol**: Acceso remoto y gestión externa

- Acceso desde cualquier lugar sin IP fija
- Autenticación y autorización
- API REST y WebSocket
- Solo necesario para acceso remoto

### 📱 Aplicación Móvil
**Rol**: Interfaz de usuario remota

- Visualización de estado del sistema
- Control remoto de dispositivos
- Configuración y ajustes
- Funciona solo cuando hay conexión internet

---

## Comunicaciones

### Local (Siempre Disponible)
- **Nodos Secundarios ↔ Nodo Principal**: BLE, Sub-GHz, u otro protocolo inalámbrico
- **Nodo Principal ↔ Gateway**: BLE, USB, u otro (a definir)

### Remoto (Opcional)
- **Gateway ↔ Cloud**: HTTPS, WebSocket
- **App Móvil ↔ Cloud**: HTTPS, WebSocket

---

## Alcance del Proyecto

### ✅ Dentro del Alcance
- Sistema domótico completamente funcional offline
- Múltiples sensores y actuadores
- Control local físico (botones/pantalla)
- Acceso remoto vía cloud
- Arquitectura modular y escalable
- Bajo consumo energético en nodos

### ❌ Fuera del Alcance (por ahora)
- Streaming de video desde dispositivos Zephyr
- Comunicación directa nodos → cloud (sin gateway)
- Configuración de IP fija residencial
- Acceso SSH desde aplicación móvil
- Integración con asistentes de voz

---

## Tecnologías Core

- **RTOS**: Zephyr RTOS
- **Gestión de código**: West (workspace propio)
- **Comunicación local**: BLE, Sub-GHz (a evaluar)
- **Backend**: Cloudflare Workers/Pages
- **Protocolos**: HTTPS, WebSocket, REST

---

## Estado Actual

📋 **Fase de Diseño**
- Arquitectura conceptual definida
- Componentes identificados
- Comunicaciones generales especificadas
- Hardware específico: en evaluación
- Protocolos detallados: en evaluación

---

## Próximos Pasos

1. Definir hardware específico para nodo principal
2. Implementar MVP: nodo principal con sensor/actuador dummy
3. Establecer comunicación BLE básica
4. Desarrollar interfaz local (display + botones)
5. Escalar a múltiples nodos secundarios
6. Agregar gateway y backend
7. Desarrollar aplicación móvil

---

## Filosofía de Desarrollo

Este proyecto se desarrolla **incrementalmente**:
- Cada fase agrega funcionalidad sin romper lo anterior
- Se valida cada componente antes de agregar el siguiente
- Las decisiones técnicas específicas se toman cuando son necesarias
- La arquitectura permite cambios sin rediseño completo
