---
{}
---

# 02.3 Manipular Objetos

En esta lección, aplicarás tus conocimientos sobre clases de Python y manipulación de objetos trabajando con una lista de instancias de **Producto**. Aprenderás cómo crear múltiples objetos, almacenarlos en una lista y encontrar el producto con el precio más alto usando las funciones integradas de Python.

## Definiendo la Clase Producto

Primero, definamos una clase sencilla `Producto` con dos atributos: `nombre` y `precio`. Estos atributos se establecerán cuando creemos cada instancia de producto.

```python
class Producto:
    def __init__(self, nombre, precio):
        self.nombre = nombre
        self.precio = precio
```

## Creando una Lista de Productos

A continuación, crearemos una lista llamada `productos` que contiene varias instancias de `Producto`. Cada producto tiene un nombre y precio únicos.

```python
productos = [
    Producto("Portátil", 999),
    Producto("Ratón", 25),
    Producto("Monitor", 350),
]
```

## Encontrando el Producto Más Caro

Para encontrar el producto con el precio más alto, usamos la función `max()` de Python combinada con una función `lambda` que extrae el atributo `precio` de cada producto.

```python
producto_mas_caro = max(productos, key=lambda p: p.precio)
print(f"{producto_mas_caro.nombre}: ${producto_mas_caro.precio}")
```

Este código imprime el nombre y precio del producto más caro en la lista.

## ¡Pruébalo Tú Mismo!

- Añade más productos a la lista `productos` con diferentes nombres y precios.
- Usa la función `min()` con una lambda similar para encontrar el producto más barato.

Ejemplo:

```python
producto_mas_barato = min(productos, key=lambda p: p.precio)
print(f"{producto_mas_barato.nombre}: ${producto_mas_barato.precio}")
```

## Por Qué Esto Importa

- **Instanciación:** Creas múltiples objetos independientes de la misma clase.
- **Colecciones:** Las listas pueden contener muchos objetos, permitiéndote gestionar grupos de datos relacionados.
- **Herramientas Funcionales:** Funciones como `max()` y `min()` combinadas con lambdas te permiten consultar fácilmente colecciones de objetos.

Este patrón es común en aplicaciones del mundo real, como plataformas de comercio electrónico donde podrías necesitar encontrar el artículo más caro o más barato en un catálogo.

## Visualizando el Concepto

![/.learn/assets/pw82l77emzr.png](/.learn/assets/pw82l77emzr.png)

¡Sigue experimentando con la creación y manipulación de listas de objetos para fortalecer tu comprensión de las capacidades orientadas a objetos de Python!