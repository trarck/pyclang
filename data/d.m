#import "d.h"

@implementation UnityAppController
@synthesize renderDelegate;

- (void)preStartUnity:(NSInteger) x aa:(float) y bb:(NSString*) str
{
    NSLog(@"%d",x);
}

- (void)shouldAttachRenderDelegate {
    // Sent when the application is about to move from active to inactive state. This can occur for certain types of temporary interruptions (such as an incoming phone call or SMS message) or when the user quits the application and it begins the transition to the background state.
    // Use this method to pause ongoing tasks, disable timers, and invalidate graphics rendering callbacks. Games should use this method to pause the game.
}

@end