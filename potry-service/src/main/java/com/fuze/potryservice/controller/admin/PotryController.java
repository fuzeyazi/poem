package com.fuze.potryservice.controller.admin;

import com.fuze.dto.PotryDTO;
import com.fuze.potryservice.Aspect.AutoLog;
import com.fuze.potryservice.service.AdminService;
import com.fuze.potryservice.service.PotryService;
import com.fuze.result.Result;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController("管理端")
@RequestMapping("/admin/potry")
@Api(tags = "诗词管理的相关接口")
@Slf4j
public class PotryController {
    @Autowired
    private  PotryService potryService;
    @Autowired
    private AdminService AdminService;
    @ApiOperation(value = "获取古诗的数量")
    @GetMapping("/GetCount")
    public Result<Integer> GetCount() {
        //直接调用
        log.info("获取现存古诗数量执行:");
        Integer count = potryService.getcount();
        return Result.success(count);
    }
    @ApiOperation(value = "添加古诗")
    @AutoLog(value = "添加古诗")
    @GetMapping("/add")
public Result add(@RequestBody PotryDTO potryDTO) {
        log.info("添加古诗执行:");
        AdminService.add(potryDTO);
        return Result.success("添加成功");
    }
    @ApiOperation(value = "批量删除古诗")
    @AutoLog(value = "删除古诗")
    @GetMapping("/delete")
    public Result delete(@RequestBody List<Long> ids) {
        log.info("批量删除古诗执行:");
        AdminService.delete(ids);
        return Result.success("删除成功");
    }
@ApiOperation(value = "修改古诗")
@AutoLog(value = "修改古诗")
    @GetMapping("/update")
    public Result update(@RequestBody PotryDTO potryDTO) {
        log.info("修改古诗执行:");
        AdminService.update(potryDTO);
        return Result.success("修改成功");
    }
}
