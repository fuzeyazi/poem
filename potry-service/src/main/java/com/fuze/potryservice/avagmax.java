package com.fuze.potryservice;

import java.lang.reflect.Array;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Scanner;

public class avagmax {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        ArrayList<Integer> list = new ArrayList<>();
        System.out.println("请输入10个整数：");
        for (int i = 0; i < 10; i++) {
            int num = scanner.nextInt();
            System.out.println("第" + (i + 1) + "个整数为：" + num);
            list.add(num);
        }
        Collections.sort(list);
        System.out.println("最大数是：" + list.get(list.size() - 1));
        System.out.println("最小数是：" + list.get(0));
       int sum=0;
        for (int i = 0; i < list.size(); i++) {
            sum+=list.get(i);
        }
        System.out.println("平均值是：" + sum / list.size());
    }
}
