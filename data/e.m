@interface UnityAppController
{
    int _myi;
    float _myf;
}

-(void) test;

@end

@implementation UnityAppController
-(void)test
{


}
@end

@interface UnityAppController(TestCat)
-(void) fun2:(int)i aa:(float) y;
@end

@implementation UnityAppController(TestCat)
-(void) fun2:(int)i aa:(float) y
{


}
@end