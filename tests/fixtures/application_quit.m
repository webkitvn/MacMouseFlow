#import <AppKit/AppKit.h>

__attribute__((constructor)) static void requestApplicationQuit(void) {
    @autoreleasepool {
        [[NSNotificationCenter defaultCenter] addObserverForName:NSApplicationDidFinishLaunchingNotification
                                                         object:nil
                                                          queue:[NSOperationQueue mainQueue]
                                                     usingBlock:^(NSNotification *notification) {
            dispatch_async(dispatch_get_main_queue(), ^{
                // The app's menu Quit consumer calls this same public AppKit action.
                fprintf(stderr, "app-action quit requested\n");
                [NSApplication.sharedApplication terminate:nil];
            });
        }];
    }
}
