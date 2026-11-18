package com.fuze.potryservice.controller.user;

import com.fuze.potry.entity.Allusion;
import com.fuze.potryservice.service.AllusionService;
import com.fuze.result.Result;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import io.swagger.annotations.ApiParam;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 诗词典故溯源前端控制器
 * 对应网关路由: /user/** -> lb://potry-service
 */
@RestController
@RequestMapping("/user/allusion")
@Api(tags = "诗词文化典故溯源微服务接口")
@Slf4j
public class AllusionController {

    @Autowired
    private AllusionService allusionService;

    /**
     * 获取全量启用的典故列表字典
     */
    @ApiOperation(value = "获取全部典故列表")
    @GetMapping("/list")
    public Result<List<Allusion>> list() {
        log.info("Request allusions list");
        List<Allusion> list = allusionService.getAllAllusions();
        return Result.success(list);
    }

    /**
     * 根据主键ID获取典故详情
     */
    @ApiOperation(value = "根据ID查询典故详情")
    @GetMapping("/{id}")
    public Result<Allusion> getById(
            @ApiParam(value = "典故ID", required = true)
            @PathVariable("id") Integer id) {
        log.info("Request allusion by id: {}", id);
        Allusion allusion = allusionService.getAllusionById(id);
        if (allusion == null) {
            return Result.error("未找到对应典故");
        }
        return Result.success(allusion);
    }

    /**
     * 根据典故名称精准获取详情
     */
    @ApiOperation(value = "根据名称查询典故详情")
    @GetMapping("/getByName")
    public Result<Allusion> getByName(
            @ApiParam(value = "典故名称，如：折柳", required = true)
            @RequestParam("name") String name) {
        log.info("Request allusion by name: {}", name);
        Allusion allusion = allusionService.getAllusionByName(name);
        if (allusion == null) {
            return Result.error("未找到对应典故");
        }
        return Result.success(allusion);
    }
}
