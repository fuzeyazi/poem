package com.fuze.potryservice;

public class Proventional {
    public static void main(String[] args) {
        Square square = new Square(10);
        Shape shape = square;
        System.out.println("正方形周长: " + shape.getPerimeter());
        System.out.println("正方形面积: " + shape.getArea());
        Circle circle = new Circle(5);
        shape = circle;
        System.out.println("圆形周长: " + shape.getPerimeter());
        System.out.println("圆形面积: " + shape.getArea());
        Rect rect = new Rect(15, 10);
        shape = rect;
        System.out.println("矩形周长: " + shape.getPerimeter());
        System.out.println("矩形面积: " + shape.getArea());
    }
}
