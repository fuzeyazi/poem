package com.fuze.potryservice;

public class tex1ta {
    public static void main(String[] args) {
        System.out.println("次数："+get9Count());

    }
    public static int get9Count() {
        int sum=0;
        for(int i=1;i<100;i++){
            if (i % 10 == 9) {
                sum++;
            }
            if (i / 10 == 9) {
                sum++;
            }
        }
        return sum;
    }
}
