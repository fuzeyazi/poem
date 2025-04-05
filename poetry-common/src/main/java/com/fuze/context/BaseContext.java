package com.fuze.context;

public class BaseContext {
       //线程安全的，每个线程都拥有自己的数据，一个用户一个线程，线程安全
    public static ThreadLocal<Long> threadLocal = new ThreadLocal<>();

    public static void setCurrentId(Long id) {
        threadLocal.set(id);
    }
    public static void setDagree(Long Dagree) {

        threadLocal.set(Dagree);
    }
    public static Long getCurrentId() {
        return threadLocal.get();
    }
    public static Long getDagree() {
        return threadLocal.get();
    }

    public static void removeCurrentId() {
        threadLocal.remove();
    }

}
