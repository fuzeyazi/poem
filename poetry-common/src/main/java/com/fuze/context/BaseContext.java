package com.fuze.context;

public class BaseContext {
    public static ThreadLocal<Long> userIdThreadLocal = new ThreadLocal<>();
    public static ThreadLocal<Long> degreeThreadLocal = new ThreadLocal<>();

    public static void setCurrentId(Long id) {
        userIdThreadLocal.set(id);
    }

    public static void setDagree(Long degree) {
        degreeThreadLocal.set(degree);
    }

    public static Long getCurrentId() {
        return userIdThreadLocal.get();
    }

    public static Long getDagree() {
        return degreeThreadLocal.get();
    }

    public static void removeCurrentId() {
        userIdThreadLocal.remove();
    }

    public static void removeDegree() {
        degreeThreadLocal.remove();
    }

    public static void removeAll() {
        userIdThreadLocal.remove();
        degreeThreadLocal.remove();
    }
}