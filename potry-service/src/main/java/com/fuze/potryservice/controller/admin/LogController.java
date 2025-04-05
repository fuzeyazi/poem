package com.fuze.potryservice.controller.admin;

import com.fuze.potryservice.service.LogService;
import com.fuze.result.PageResult;
import com.fuze.result.Result;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/admin/log")
@Slf4j
@Api(tags = "日志管理")
public class LogController {
    @Autowired
    private LogService LogService;
    @Autowired
    private LogService logService;

    @ApiOperation("获取日志(分页展示一页十条)")
    @RequestMapping("/get")
    public Result<PageResult> GetLog(
            @RequestParam(defaultValue = "1") Integer pageNum,
            @RequestParam(defaultValue = "10") Integer pageSize
    ) {
        PageResult pageInfo = logService.GetLog(pageNum, pageSize);
        return Result.success(pageInfo);
    }

}
