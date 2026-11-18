package com.fuze.potryservice;

import lombok.Data;

@Data
public class Rect extends Shape{
    private double length;
    private double width;

    public Rect(double length, double width) {
        this.length = length;
        this.width = width;
    }
    @Override
    public double getPerimeter() {
        return 2*(length+width);
    }

    @Override
    public double getArea() {
        return length*width;
    }
}
