# Compliance Checks

Sistema modular de chequeos de cumplimiento para el proyecto oxycontroller.

## Requisitos

### Sistema Base
- **Python**: 3.12.3 
- **Perl**: Para checkpatch.pl
- **Node.js**: v20.19.4 (para DeviceTree linting)
- **npm**: 10.8.2

### Dependencias Python

Instalar o verificar con pip, versiones usadas en el desarrollo:
```
pylint==4.0.4
yamllint==1.37.1
python-magic==0.4.27
unidiff==0.7.5
junitparser==4.0.2
python-dotenv>=1.0.0
```

### Herramientas Externas

#### Ruff (Linter/Formatter de Python)
```bash
# Instalación via snap (V.0.14.9 sugerida)
snap install ruff
```

#### Clang-format (Formateador de C/C++)
```bash
# Versión más atual posible
apt install clang-format
```

#### Coccinelle (Análisis semántico de C)
```bash
# Versión requerida: 1.3.1 o superior

# Instalar dependencias
sudo apt install -y build-essential ocaml ocaml-findlib libnum-ocaml-dev \
    menhir libpcre3-dev python3-dev pkg-config autoconf automake git

# Clonar el repositorio oficial
cd /tmp
git clone https://github.com/coccinelle/coccinelle.git
cd coccinelle

# Ver la última versión disponible (1.3.1 o superior)
git tag

git checkout 1.3.1

# Configurar y compilar
./autogen
./configure --prefix=/usr
make -j$(nproc)

# Instalar
sudo make install

# Verificar
spatch --version
```

#### dts-linter (Linter de DeviceTree)
```bash
# Instalación local
cd oxycontroller/scripts/checks
npm ci
```

#### CodeChecker (Análisis estático C/C++)
```bash
# Instalación via pip
pip install codechecker

# Verificar
CodeChecker version
```

### Verificar instalación

```bash
python3 scripts/checks/check_compliance.py --list
```

## Uso

### Sintaxis Básica

```bash
python3 scripts/checks/check_compliance.py [opciones]
```

### Opciones Principales

- `-m, --module <NOMBRE>`: Ejecutar chequeo específico
- `-c, --commits <RANGE>`: Modo diff - analiza archivos en un rango de commits (ej: `HEAD~1` para el último commit)
- `-p, --paths <PATH>`: Analizar directorios/archivos específicos
- `-o, --output <FILE>`: Archivo de salida XML (JUnit format)
- `-n, --no-case-output`: No genera archivos .txt con resumen por cada herramienta aplicada.
- `-l, --list`: Listar chequeos disponibles
- `-v, --loglevel <LEVEL>`: Nivel de logging (DEBUG, INFO, WARNING, ERROR)
- `-e, --exclude <NOMBRE>`: Excluir chequeo específico
- `-j, --previous-run <FILE>`: Combinar resultados de múltiples ejecuciones
- `--annotate`: Generar anotaciones para GitHub Actiones

##  Chequeos Disponibles

### 1. **ClangFormat**
Verifica formato de código C/C++ con clang-format.

**Archivos analizados**: `.c`, `.h`
**Dependencias**: clang-format
**Configuración**: `.clang-format`

### 2. **Checkpatch**
Ejecuta checkpatch.pl de Zephyr para verificar estilo de código.

**Archivos analizados**: `.c`, `.h`, `.cpp`, `.hpp`, `.cc`, `.S`, `.s`, `.inc`
**Dependencias**: Perl, Zephyr (`deps/zephyr/scripts/checkpatch.pl`)
**Configuración**: `.checkpatch.conf`

### 3. **CMakeStyle**
Verifica estilo de archivos CMake.

**Archivos analizados**: `.cmake`, `CMakeLists.txt`
**Dependencias**: N/A
**Configuración**: N/A
**Reglas**:
- No usar tabulaciones (solo espacios)
- No poner espacio antes de `(` en `if()`

### 4. **DevicetreeBindings**
Verifica propiedades de Device Tree bindings.

**Archivos analizados**: `dts/bindings/**/*.yaml`
**Dependencias**: Zephyr (edtlib)
**Configuración**: `bindings_properties_allowlist.yaml` (opcional)
**Verifica**:
- Nombres de propiedades sin guiones bajos
- `required: false` redundante

### 5. **YAMLLint**
Verifica sintaxis y estilo de archivos YAML.

**Archivos analizados**: `.yaml`, `.yml`
**Dependencias**: yamllint
**Configuración**: `.yamllint`

### 6. **Kconfig**
Verifica configuraciones Kconfig y referencias CONFIG_*.

**Archivos analizados**: `Kconfig*`, archivos fuente con `CONFIG_*`
**Dependencias**: Zephyr (kconfiglib, scripts)
**Configuración**: Múltiples archivos Kconfig del proyecto
**Importante**: No soporta modo diff (requiere análisis completo por aplicación)

### 7. **Pylint**
Ejecuta pylint en archivos Python.

**Archivos analizados**: `.py`, scripts Python
**Dependencias**: pylint, Zephyr (checkers adicionales)
**Configuración**: `.pylintrc`

### 8. **Ruff**
Linter y formateador de Python (más rápido que pylint).

**Archivos analizados**: `.py`, `.pyi`
**Dependencias**: ruff
**Configuración**: `.ruff.toml`
**Ejecuta**: `ruff check` + `ruff format --diff`

### 9. **Coccinelle**
Análisis semántico de código C con reglas de Coccinelle.

**Archivos analizados**: `.c`, `.h`
**Dependencias**: Coccinelle (spatch), Zephyr (scripts/coccinelle)
**Configuración**: Reglas .cocci de Zephyr
**Reglas incluidas**: 16 reglas (array_size, boolean, deref_null, etc.)

### 10. **DevicetreeLinting**
Linter de sintaxis y formato para archivos DeviceTree.

**Archivos analizados**: `.dts`, `.dtsi`, `.overlay`
**Dependencias**: Node.js, npm, dts-linter
**Configuración**: Detecta aplicaciones (con `prj.conf` o `CMakeLists.txt`)
**Output**: Genera parche `dts_linter.patch` con correcciones

### 11. **CodeChecker**
Análisis estático de código C/C++ (Clang Static Analyzer, Clang-Tidy, Cppcheck).

**Archivos analizados**: `.c`, `.h`, `.cpp`, `.hpp`, `.cc`, `.S`, `.s`, `.inc`
**Dependencias**: CodeChecker, west, compile_commands.json
**Configuración**: `.codechecker.skip`

##  Modos de Análisis

### Listar Herramientas
Lista las herramientas que están disponibles para usar:

```bash
python3 scripts/checks/check_compliance.py -l
```

### Modo DEFAULT (sin flags)
Analiza directorios predeterminados: `node/` y `lora_gateway/`

```bash
python3 scripts/checks/check_compliance.py
```
Ejeucta cada uno de los chequeos y genera un archivo .txt por cada uno de éstos.

### Modo PATH (`-p`)
Analiza directorios/archivos específicos:

```bash
python3 scripts/checks/check_compliance.py -m ruff -p node/src -p lora_gateway/
```

### Modo DIFF (`--commits`)
Analiza solo archivos modificados en commits:

```bash
# Último commit
python3 scripts/checks/check_compliance.py -m clangformat -c HEAD~1

# Rango de commits
python3 scripts/checks/check_compliance.py -m checkpatch -c HEAD~3..HEAD
```

**Nota**: Kconfig no soporta modo DIFF (requiere análisis completo del árbol)


### Ejecutar múltiples chequeos

```bash
# C/C++: clangformat + checkpatch
python3 scripts/checks/check_compliance.py -m clangformat -m checkpatch

# Todo Python en node/
python3 scripts/checks/check_compliance.py -m pylint -m ruff -p node/
```

## Salida y Reportes

### Formato de Salida

Por defecto, los resultados se muestran en consola. Con `-o`, se puede especificar el nombre del archivo generado XML en formato JUnit (por default `compliance.xml`):

```bash
python3 check_compliance.py -c pylint -o results.xml
```
También genera archivos .txt por defecto por cada herramienta, se puede evitar especificando `-n`

### Logs

Niveles de logging:
- `ERROR`: Solo errores críticos
- `WARNING`: Advertencias y errores
- `INFO`: Información general (default)
- `DEBUG`: Información detallada de ejecución

```bash
python3 check_compliance.py -m ruff -v DEBUG
```

##  Notas

- **Kconfig**: Análisis global, no soporta modo diff
- **DevicetreeLinting**: Detecta automáticamente aplicaciones Zephyr
- **Coccinelle**: Genera `function_names.pickle` en primera ejecución (puede tardar)
- **CodeChecker**: Requiere build de aplicación Zephyr (genera `compile_commands.json`)
