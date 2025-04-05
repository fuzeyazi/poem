package com.fuze.vo;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalTime;
import java.util.List;

@Data
@Builder
@AllArgsConstructor
@NoArgsConstructor
public class PlanDataVo {
    List<Integer> sum;
    List<LocalTime> time;

    //如果是0，则表示未学习，1表示学习中，2表示已学习
    List<Integer> isReview;
}
