package com.fuze.utils;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

public class EbbinghausScheduler {
    private static final List<Integer> INTERVALS = null;
    private List<LocalDate> reviewDates;
    private int currentIndex;
    public EbbinghausScheduler(LocalDate startDate) {
        this.reviewDates = new ArrayList<>();
        this.reviewDates.add(startDate);
        this.currentIndex = 0;
    }
    public LocalDate getNextReviewDate() {
        if (currentIndex < INTERVALS.size()) {
            int intervalDays = INTERVALS.get(currentIndex);
            LocalDate nextReviewDate = reviewDates.get(reviewDates.size() - 1).plusDays(intervalDays);
            reviewDates.add(nextReviewDate);
            currentIndex++;
            return nextReviewDate;
        } else {
            // 所有预设的复习间隔都已用完，可以抛出异常或返回null，这里选择返回null
            return null;
        }
    }


}
