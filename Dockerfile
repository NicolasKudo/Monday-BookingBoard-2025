# Usa una imagen más liviana para reducir tamaño y tiempos de despliegue
FROM python:3.11

# Establece el directorio de trabajo en el contenedor
WORKDIR /app

# Copia solo el requirements.txt primero para aprovechar cacheo en la construcción
COPY requirements.txt ./

# Instala las dependencias de Python sin cache para evitar archivos innecesarios
RUN pip install --no-cache-dir -r requirements.txt

# Luego, copia el código fuente después de instalar dependencias
COPY . .

# Exponer el puerto 8080 para Cloud Run o cualquier servicio web
EXPOSE 8080

# Definir el comando de ejecución de la aplicación con Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "--timeout", "300", "--workers", "1", "--preload", "--max-requests", "1", "main:app"]
