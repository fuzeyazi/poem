package com.fuze.potryservice.Aspect;

import com.fuze.context.BaseContext;
import com.fuze.dto.UserLogin;
import com.fuze.potryservice.mapper.UserMapper;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.After;
import org.aspectj.lang.annotation.AfterReturning;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Pointcut;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Aspect
@Component
public class MorentouAspect {
    @Autowired
    private UserMapper userMapper;
   @Pointcut("@annotation(com.fuze.potryservice.Aspect.Autozuru)")
    private void pointcut(){}

@AfterReturning(pointcut = "pointcut()")
    private String addtouxiang(){
  try{
         long idd= BaseContext.getCurrentId();
         int id= (int)idd;
         String touxiang=userMapper.gettouxiangbyid(id);
         if(touxiang==null){
         String url="https://webxiangmu.oss-cn-beijing.aliyuncs.com/lun/40e10c38-4470-4832-be75-67af2861e0e1.png";
         String name="不吃香菜"+"（哈基米版#"+id+")";
    UserLogin userLogin=new UserLogin();
    userLogin.setId(id);
    userLogin.setName(name);
    userLogin.setTouxiang(url);
         userMapper.updatemessagebyid213(userLogin);
         return "添加成功";}
         else{
             return "无需添加";
         }
    }catch (Exception e){
        return "添加失败";
  }
   }
}
